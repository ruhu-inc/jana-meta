"""The research agent on the device (SPEC §18): the short conversation, then a study pack made from the web.

    POST /v1/study/research/chat              one turn of the conversation (the app keeps the turns so far)
    POST /v1/study/research                   start research on the approved brief (202, a Record)
    GET  /v1/study/research[/{research_id}]   the packs, each brought up to date when read
    POST /v1/study/research/{research_id}/cancel

The gateway's job searches and fetches the pages; when they arrive they become one Study text source ("Web research:
…", one section per page with its URL) and each part the brief asked for is an ordinary Study job on it, so every
claim is checked against its cited passages as any Study aid is (the gateway's support verifier). A photographed
diagram's pack also keeps its capture for the diagram drill. The conversation's text never leaves the device again:
the job receives the brief's fields and the photo's confirmed part names only. A pack is brought up to date when it
is read (the app polls while it shows one), so a restart or an offline spell only delays it.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request, Response

from agent_core.api.core import CoreService
from agent_core.api.errors import ApiError
from agent_core.contracts import errors as contract_errors
from agent_core.engine.events import new_id
from agent_core.engine.research_chat import ChatError, Start, next_turn
from agent_core.engine.safety import redact_personal
from agent_core.engine.study import StudyDesk, StudyError
from agent_core.net.study import StudyCloudError

RESEARCH = "study/research#/$defs/"
SOURCE_CHARS = 195_000  # within a Study text source's 200,000 characters, with room for the headings
PART_KINDS = ("concept_map", "notes", "flashcards", "quiz", "audio_overview")
CODE_MARKED = ["choice", "true_false", "multi_select", "fill_blank", "numeric"]  # SPEC §18.1: no worded answers
LIVE = ("sending", "waiting_online", "researching", "making")


def page_sections(title: str, brief: dict[str, Any], pages: list[dict[str, Any]]) -> str:
    """The researched pages as one Study source: each page keeps its title, site and URL above its text, so every
    citation shows where it came from; long pages share what room is left after the short ones."""
    head = (f"Web research: {title}\nFound by Jana's research agent for these questions:\n"
            + "\n".join(f"- {q}" for q in brief["sub_questions"]))  # fmt: skip
    room = SOURCE_CHARS - len(head)
    order = sorted(range(len(pages)), key=lambda i: len(pages[i]["text"]))
    share = [0] * len(pages)
    for left, i in enumerate(order):
        share[i] = min(len(pages[i]["text"]), max(0, room // (len(pages) - left)))
        room -= share[i]
    sections = [
        f"## {n}. {page['title']}\nSource URL: {page['url']}\nSite: {page['site']}\n\n{page['text'][:share[n - 1]]}"
        for n, page in enumerate(pages, 1)
        if share[n - 1] > 0
    ]
    return "\n\n".join([head, *sections])


def part_request(kind: str, source: dict[str, Any], brief: dict[str, Any]) -> dict[str, Any]:
    """The Study job for one part of the pack, scoped by the brief (its focus, its length)."""
    selection = {"source_id": source["source_id"], "revision": source["revision"]}
    body: dict[str, Any] = {"kind": kind, "sources": [selection], "execution": "prefer_cloud"}
    long = brief["length"] == "long"
    settings: dict[str, Any] = {}
    if brief["focus"] and kind != "concept_map":
        settings["focus"] = brief["focus"][:500]
    if kind == "flashcards":
        body["count"] = 20 if long else 10
    if kind == "quiz":
        body["count"] = 10
        settings["question_types"] = CODE_MARKED
    if kind == "audio_overview":
        settings["podcast_length"] = "standard" if long else "short"
    if settings:
        body["settings"] = settings
    return body


def photo_parts(core: CoreService, capture_id: str) -> tuple[str | None, tuple[str, ...]]:
    """A confirmed photographed diagram's title and part names (the diagram drill's reading, SPEC §5.2)."""
    desk = getattr(core, "capture_desk", None)
    if desk is None:
        raise ApiError("not_found")
    record = desk.get(capture_id)
    if record["purpose"] != "diagram" or record["status"] != "confirmed":
        raise ApiError("validation_failed", details={"reason": "diagram_not_confirmed"})
    named = [r["text"].strip() for r in record["regions"] if r["kind"] == "diagram" and "[?]" not in r["text"]]
    names = tuple(dict.fromkeys(n for n in named if n))
    if not names:
        raise ApiError("validation_failed", details={"reason": "diagram_not_confirmed"})
    return None, names[:24]


def add_routes(app: FastAPI, core: CoreService, desk: Callable[[], StudyDesk],
               command: Callable[..., Awaitable[Response]], fail: Callable[[StudyError], ApiError],
               response: Callable[..., Response]) -> None:  # fmt: skip
    def cloud() -> Any:
        if core.study.cloud is None:
            raise StudyError("consent_required")
        return core.study.cloud

    def load(d: StudyDesk, research_id: str) -> tuple[dict[str, Any], str | None]:
        row = d.conn.execute("SELECT body,gateway_id FROM study_research WHERE research_id=?",
                             (research_id,)).fetchone()  # fmt: skip
        if row is None:
            raise StudyError("not_found")
        return json.loads(row[0]), row[1]

    def save(d: StudyDesk, record: dict[str, Any], gateway_id: str | None) -> dict[str, Any]:
        record["updated_at"] = core.clock_ms()
        if contract_errors(RESEARCH + "Record", record):
            raise StudyError("invalid_study_request")
        d.conn.execute("UPDATE study_research SET body=?,gateway_id=?,updated_at=? WHERE research_id=?",
                       (json.dumps(record), gateway_id, record["updated_at"], record["research_id"]))  # fmt: skip
        return record

    async def send(d: StudyDesk, record: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        """The brief to the gateway; offline it waits, refused it fails with the reason."""
        parts: tuple[str, ...] = ()
        if record["capture_id"]:
            _, parts = photo_parts(core, record["capture_id"])
        try:
            job = await cloud().research_start(d.conn, {"brief": record["brief"], "photo_parts": list(parts)})
        except (StudyCloudError, StudyError) as error:
            reason = getattr(error, "reason", "upstream")
            if reason == "waiting_online":
                return {**record, "status": "waiting_online"}, None
            failure = reason if reason in ("consent_required", "allowance_exhausted") else "upstream"
            return {**record, "status": "failed", "failure": failure}, None
        return {**record, "status": "researching", "sub_questions": job["sub_questions"]}, job["research_id"]

    def make(d: StudyDesk, record: dict[str, Any], pages: list[dict[str, Any]]) -> dict[str, Any]:
        """The pages as one Study source, and a Study job for each part the brief asked for."""
        brief = record["brief"]
        text, _ = redact_personal(page_sections(brief["title"], brief, pages))
        source = d.create({"kind": "text", "title": f"Web research: {brief['title']}"[:200], "text": text})
        parts = []
        for kind in [k for k in PART_KINDS if k in brief["outputs"]]:
            try:
                job = d.create_job(part_request(kind, source, brief))
                parts.append({"kind": kind, "job_id": job["job_id"], "aid_id": None, "state": "making"})
            except StudyError:
                parts.append({"kind": kind, "job_id": None, "aid_id": None, "state": "failed"})
        core.study.poll()
        return {**record, "status": "making", "pages": len(pages), "source_id": source["source_id"], "parts": parts}

    def settle(d: StudyDesk, record: dict[str, Any]) -> dict[str, Any]:
        """Each part follows its Study job; the pack is ready once none is still being made."""
        parts = []
        for part in record["parts"]:
            if part["state"] == "making" and part["job_id"]:
                job = d.job(part["job_id"])
                if job["state"] == "completed" and job["result_ids"]:
                    part = {**part, "state": "ready", "aid_id": job["result_ids"][0]}
                elif job["state"] in ("failed", "cancelled"):
                    part = {**part, "state": "failed"}
            parts.append(part)
        done = all(p["state"] in ("ready", "failed") for p in parts)
        return {**record, "parts": parts, "status": "ready" if done else "making"}

    async def refresh(d: StudyDesk, research_id: str) -> dict[str, Any]:
        record, gateway_id = load(d, research_id)
        if record["status"] in ("sending", "waiting_online") and gateway_id is None:
            record, gateway_id = await send(d, record)
        elif record["status"] == "researching" and gateway_id is not None:
            try:
                job = await cloud().research_job(d.conn, gateway_id)
            except StudyCloudError as error:
                if error.reason == "research_not_found":  # the gateway lost it (a 24-hour expiry, a reset)
                    record = {**record, "status": "failed", "failure": "interrupted"}
                return save(d, record, gateway_id)
            record = {**record, "sub_questions": job["sub_questions"]}
            if job["status"] == "ready" and job["pages"]:
                try:
                    record = make(d, record, job["pages"])
                except StudyError:
                    record = {**record, "status": "failed", "failure": "import_failed"}
                try:
                    await cloud().research_forget(d.conn, gateway_id)  # the pages are kept here now
                except (StudyCloudError, StudyError):
                    pass  # the gateway deletes them itself within 24 hours
            elif job["status"] in ("failed", "cancelled"):
                record = {**record, "status": job["status"], "failure": job["failure"]}
        if record["status"] == "making":
            record = settle(d, record)
        return save(d, record, gateway_id)

    async def guarded(run: Callable[[StudyDesk], Awaitable[Any]]) -> Response:
        try:
            return response(await run(desk()))
        except StudyError as error:
            raise fail(error) from None

    @app.post("/v1/study/research/chat")
    async def chat(request: Request) -> Response:
        async def run(d: StudyDesk, body: dict[str, Any]) -> dict[str, Any]:
            try:
                cloud().guard(d.conn)  # consent, subscription: the conversation is online as the research is
            except StudyCloudError as error:
                raise StudyError(error.reason) from None
            start = body["start"]
            if "capture_id" in start:
                title, parts = photo_parts(core, start["capture_id"])
                subject = Start(photo_title=title, photo_parts=parts)
            else:
                subject = Start(topic=start["topic"])
            router = core.research_router() if core.research_router is not None else None
            if router is None:
                raise ApiError("model_unavailable")
            try:
                return await next_turn(router, subject, body["history"], body["answer"], body["skip"])
            except ChatError as error:
                raise ApiError("model_unavailable", details={"reason": str(error)}) from None

        return await command(request, "study/research#/$defs/ChatRequest", run, atomic_command=False)

    @app.post("/v1/study/research")
    async def create(request: Request) -> Response:
        async def run(d: StudyDesk, body: dict[str, Any]) -> dict[str, Any]:
            brief = dict(body["brief"])
            if body["capture_id"]:
                photo_parts(core, body["capture_id"])  # a confirmed diagram, or refused before anything is sent
            else:
                brief["outputs"] = [o for o in brief["outputs"] if o != "diagram_drill"] or ["notes"]
            now = core.clock_ms()
            record = {"research_id": new_id("rsr"), "status": "sending", "brief": brief,
                      "capture_id": body["capture_id"], "failure": None, "source_id": None, "pages": 0, "parts": [],
                      "sub_questions": [{"text": q, "state": "waiting", "sources": 0} for q in brief["sub_questions"]],
                      "created_at": now, "updated_at": now}  # fmt: skip
            if contract_errors(RESEARCH + "Record", record):
                raise StudyError("invalid_study_request")
            d.conn.execute("INSERT INTO study_research VALUES (?,?,?,?,?)",
                           (record["research_id"], None, json.dumps(record), now, now))  # fmt: skip
            record, gateway_id = await send(d, record)
            return save(d, record, gateway_id)

        return await command(request, "study/research#/$defs/CreateRequest", run, status=202,
                             atomic_command=False)

    @app.get("/v1/study/research")
    async def listed() -> Response:
        async def run(d: StudyDesk) -> dict[str, Any]:
            rows = d.conn.execute("SELECT body FROM study_research ORDER BY created_at DESC, research_id DESC "
                                  "LIMIT 200").fetchall()  # fmt: skip
            return {"items": [json.loads(r[0]) for r in rows]}

        return await guarded(run)

    @app.get("/v1/study/research/{research_id}")
    async def one(research_id: str) -> Response:
        async def run(d: StudyDesk) -> dict[str, Any]:
            return await refresh(d, research_id)

        return await guarded(run)

    @app.post("/v1/study/research/{research_id}/cancel")
    async def cancel(research_id: str, request: Request) -> Response:
        async def run(d: StudyDesk, _: Any) -> dict[str, Any]:
            record, gateway_id = load(d, research_id)
            if record["status"] not in ("sending", "waiting_online", "researching"):
                raise StudyError("invalid_study_request", True)  # making or done: the Study jobs are the parts now
            if gateway_id is not None:
                try:
                    await cloud().research_cancel(d.conn, gateway_id)
                except StudyCloudError:
                    pass  # the gateway stops at its own limits; nothing more is fetched for this pack here
            return save(d, {**record, "status": "cancelled"}, gateway_id)

        return await command(request, None, run, atomic_command=False)
