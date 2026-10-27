"""The research agent on the device (SPEC §18), through the real routes with the gateway and the model scripted:
the conversation, then a pack made from the web. The brief (never the conversation) goes to the gateway; the pages
become one Study text source with each page's URL; each part the brief asked for is a Study job on it; the pack is
ready once its parts are made. Offline it waits; refused, it fails with the reason. Every page and reply is
synthetic."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from agent_core.config import Settings
from agent_core.contracts import errors
from agent_core.net.study import StudyCloudError

ULID = "01J8Z5W6X7Y8Z9A0B1C2D3E4F5"
GATEWAY_ID = f"rsj_{ULID}"
BRIEF = {"title": "How the heart pumps blood", "subject": "biology", "level": "o_level", "purpose": "exam",
         "known": "the four chambers", "focus": "the valves",
         "sub_questions": ["What do the heart valves do?", "How does the left ventricle pump blood?",
                           "What is the cardiac cycle?", "Why is the left ventricle wall thicker?"],
         "outputs": ["concept_map", "flashcards", "quiz", "diagram_drill"], "length": "short"}  # fmt: skip
PAGES = [
    {"url": "https://example.org/heart-valves", "title": "Heart valves", "site": "example.org", "sub_question": 0,
     "text": "The heart valves open and close to keep blood flowing one way. " * 20, "fetched_at": 1},
    {"url": "https://example.edu/cardiac-cycle", "title": "The cardiac cycle", "site": "example.edu",
     "sub_question": 2, "text": "Each heartbeat is one cardiac cycle of systole and diastole. " * 20,
     "fetched_at": 1},
    {"url": "https://example.edu/ventricles", "title": "Ventricles", "site": "example.edu", "sub_question": 3,
     "text": "The left ventricle pumps blood to the whole body. " * 20, "fetched_at": 1},
]  # fmt: skip


def job(status: str, pages: list[dict[str, Any]] | None = None, failure: str | None = None) -> dict[str, Any]:
    return {"research_id": GATEWAY_ID, "status": status, "failure": failure, "pages": pages, "created_at": 1,
            "updated_at": 2,
            "sub_questions": [{"text": q, "state": "done" if status == "ready" else "searching", "sources": 1}
                              for q in BRIEF["sub_questions"]]}  # fmt: skip


@dataclass
class Gateway:
    """The gateway's research job and Study processing as the device sees them."""

    states: list[dict[str, Any]] = field(default_factory=list)
    started: list[dict[str, Any]] = field(default_factory=list)
    forgotten: list[str] = field(default_factory=list)
    refuse: str | None = None

    def guard(self, conn: Any) -> str:
        return "profile"

    async def research_start(self, conn: Any, request: dict[str, Any]) -> dict[str, Any]:
        if self.refuse:
            raise StudyCloudError(self.refuse)
        self.started.append(request)
        return job("queued")

    async def research_job(self, conn: Any, research_id: str) -> dict[str, Any]:
        assert research_id == GATEWAY_ID
        return self.states.pop(0)

    async def research_cancel(self, conn: Any, research_id: str) -> dict[str, Any]:
        return job("cancelled")

    async def research_forget(self, conn: Any, research_id: str) -> None:
        self.forgotten.append(research_id)

    async def process(self, *args: Any, **kwargs: Any) -> Any:
        raise StudyCloudError("waiting_online")  # the parts' Study jobs stay queued: this test finishes them itself


@dataclass
class Result:
    structured: Any
    schema_valid: bool = True


@dataclass
class Router:
    replies: list[Any]
    prompts: list[str] = field(default_factory=list)

    async def complete(self, role: str, messages: list[Any], tools: Any = (), **kw: Any) -> Result:
        self.prompts.append(messages[0].content)
        return Result(self.replies.pop(0))


def scenario(tmp_path: Any, play: Any) -> None:
    from api_harness import cli, start_core, stop_core
    from test_m10a_profiles import Api, student

    async def go() -> None:
        r = await start_core(tmp_path, settings=Settings(worker_pool_size=1, worker_respawn_backoff_s=(0.0,),
                                                         api_command_burst_per_s=1000, study_workspace_enabled=True),
                             worker=False)  # fmt: skip
        try:
            api = Api(r)
            token = (await api.unlock(await api.add(student("Ama")))).json()["profile_token"]

            async def send(method: str, path: str, body: Any = None) -> Any:
                return await api.call(method, path, body, profile=token, headers={"idempotency-key": cli()})

            async def get(path: str) -> Any:
                return await api.call("GET", path, profile=token)

            gateway = Gateway()
            r.core.study.cloud = gateway
            await play(r, send, get, gateway)
        finally:
            await stop_core(r)

    asyncio.run(go())


def test_the_conversation_then_a_pack_made_from_the_web(tmp_path: Any) -> None:
    async def play(r: Any, send: Any, get: Any, gateway: Gateway) -> None:
        question = {"kind": "question", "question": "What is this pack for?", "chips": ["An exam", "Curiosity"],
                    "asks": "purpose", "brief": None}  # fmt: skip
        router = Router([question])
        r.core.research_router = lambda: router
        turn = await send("POST", "/v1/study/research/chat",
                          {"start": {"topic": "how the heart pumps blood"}, "history": [], "answer": None,
                           "skip": False})  # fmt: skip
        assert turn.status_code == 200, turn.text
        assert turn.json()["asks"] == "purpose" and "how the heart pumps blood" in router.prompts[0]

        made = await send("POST", "/v1/study/research", {"brief": BRIEF, "capture_id": None})
        assert made.status_code == 202, made.text
        record = made.json()
        assert record["status"] == "researching" and not errors("study/research#/$defs/Record", record)
        assert "diagram_drill" not in record["brief"]["outputs"], "no photo, no diagram drill"
        assert gateway.started == [{"brief": record["brief"], "photo_parts": []}], "the brief only, no conversation"

        gateway.states = [job("researching"), job("ready", PAGES)]
        still = (await get(f"/v1/study/research/{record['research_id']}")).json()
        assert still["status"] == "researching" and still["sub_questions"][0]["state"] == "searching"
        making = (await get(f"/v1/study/research/{record['research_id']}")).json()
        assert making["status"] == "making" and making["pages"] == 3 and gateway.forgotten == [GATEWAY_ID]
        assert [p["kind"] for p in making["parts"]] == ["concept_map", "flashcards", "quiz"]
        assert all(p["state"] == "making" and p["job_id"] for p in making["parts"])

        conn = r.core.study.desk().conn
        chunks = conn.execute("SELECT body FROM study_chunks WHERE source_id=?", (making["source_id"],)).fetchall()
        text = "".join(json.loads(c[0])["text"] for c in chunks)
        assert "Source URL: https://example.org/heart-valves" in text and "## 2. The cardiac cycle" in text
        quiz = next(p for p in making["parts"] if p["kind"] == "quiz")
        body = json.loads(conn.execute("SELECT checkpoint FROM study_jobs WHERE job_id=?",
                                       (quiz["job_id"],)).fetchone()[0])  # fmt: skip
        assert body["request"]["settings"]["question_types"] == ["choice", "true_false", "multi_select",
                                                                 "fill_blank", "numeric"]  # fmt: skip

        for part, state in zip(making["parts"], ("completed", "completed", "failed"), strict=True):
            jid = part["job_id"]
            row = json.loads(conn.execute("SELECT body FROM study_jobs WHERE job_id=?", (jid,)).fetchone()[0])
            row.update(state=state, result_ids=[f"aid_{ULID}"] if state == "completed" else [])
            conn.execute("UPDATE study_jobs SET state=?,body=? WHERE job_id=?", (state, json.dumps(row), jid))
        done = (await get(f"/v1/study/research/{record['research_id']}")).json()
        assert done["status"] == "ready"
        assert [p["state"] for p in done["parts"]] == ["ready", "ready", "failed"]
        assert done["parts"][0]["aid_id"] == f"aid_{ULID}"
        listed = (await get("/v1/study/research")).json()
        assert [x["research_id"] for x in listed["items"]] == [record["research_id"]]

    scenario(tmp_path, play)


def test_offline_it_waits_and_refused_it_fails_with_the_reason(tmp_path: Any) -> None:
    async def play(r: Any, send: Any, get: Any, gateway: Gateway) -> None:
        gateway.refuse = "waiting_online"
        waiting = (await send("POST", "/v1/study/research", {"brief": BRIEF, "capture_id": None})).json()
        assert waiting["status"] == "waiting_online" and gateway.started == []
        gateway.refuse = None
        resumed = (await get(f"/v1/study/research/{waiting['research_id']}")).json()
        assert resumed["status"] == "researching" and len(gateway.started) == 1

        gateway.refuse = "allowance_exhausted"
        refused = (await send("POST", "/v1/study/research", {"brief": BRIEF, "capture_id": None})).json()
        assert refused["status"] == "failed" and refused["failure"] == "allowance_exhausted"

        gateway.refuse = None
        started = (await send("POST", "/v1/study/research", {"brief": BRIEF, "capture_id": None})).json()
        cancelled = await send("POST", f"/v1/study/research/{started['research_id']}/cancel", {})
        assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
        again = await send("POST", f"/v1/study/research/{started['research_id']}/cancel", {})
        assert again.status_code == 409

        gateway.states = [job("failed", failure="no_sources")]
        other = (await send("POST", "/v1/study/research", {"brief": BRIEF, "capture_id": None})).json()
        failed = (await get(f"/v1/study/research/{other['research_id']}")).json()
        assert failed["status"] == "failed" and failed["failure"] == "no_sources"
        assert (await get(f"/v1/study/research/rsr_{ULID}")).status_code == 404

    scenario(tmp_path, play)


def test_a_diagram_pack_needs_a_confirmed_diagram_capture(tmp_path: Any) -> None:
    async def play(r: Any, send: Any, get: Any, gateway: Gateway) -> None:
        missing = await send("POST", "/v1/study/research", {"brief": BRIEF, "capture_id": f"cap_{ULID}"})
        assert missing.status_code == 404 and gateway.started == []

    scenario(tmp_path, play)
