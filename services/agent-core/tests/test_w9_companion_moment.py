"""SPEC §20.9 `test_w9_companion_moment.py` (W9): a timestamp is one number labelled `moment` and binds to a tool
result that gave it; a `study_search` hit from a lecture carries its locator and moment, and `open_moment` resolves
to the hit's source and time; Ask about this moment puts the ±30 s lines in the next turn's fence under
`study_materials` only (the moment itself as a labelled fact either way) and the context is discarded after one
turn; "what haven't I got yet" is a code fact set from the outline's skills and the learner's bands, with labelled
counts a reply can name, and a reply the gates refuse twice falls back to a code-built line from that fact set, never
the canned line (live-run fix 2026-11-01). Synthetic data."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from agent_core.config import Settings
from agent_core.engine import companion_facts
from agent_core.engine.companion import (
    action_event,
    fact_binding_errors,
    labelled_numbers,
    records_fence,
    resolve_action,
    strip_for_cloud,
)
from agent_core.engine.memory_session import MemoryAccess, SessionMemory
from agent_core.engine.memory_tools import StudyTools
from agent_core.engine.study import StudyDesk
from agent_core.store.ids import new_ulid
from memory_harness import PROFILE_A, store
from test_w8_companion import _Context, _user
from test_w8_companion_followups import _companion_traces
from w8_companion_harness import Thread, run, stop_core, thread, turn

PANEL = (Path(__file__).parent / "fixtures" / "w9" / "youtube_panel_projectile.txt").read_text()
URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
RANGE, FLIGHT = "kc.phy.o.motion.average_speed", "kc.phy.o.motion.free_fall"  # pack skills the outline names


def video(desk: StudyDesk) -> dict[str, Any]:
    return desk.create({"kind": "video_link", "url": URL, "transcript": PANEL, "title": "Projectile motion"})


def tools_over(held: Any) -> StudyTools:
    memory = SessionMemory(MemoryAccess(PROFILE_A, held.source), Settings(), "ses_" + "0" * 26)
    return StudyTools(memory, Settings(), lambda: False)


def test_a_timestamp_is_one_number_labelled_moment_and_binds_to_the_tool_result_that_gave_it() -> None:
    assert labelled_numbers("Where she derives it, at 04:12.") == [("4:12", frozenset({"moment"}))]
    assert labelled_numbers("Spots at 1:04:12 and 4:12") == [("1:04:12", frozenset({"moment"})),
                                                              ("4:12", frozenset({"moment"}))]  # fmt: skip
    # The moment binds to a result that gave it; a moment no result gave fails the gate; other numbers are unchanged.
    hit = {"items": [{"ref": 1, "moment": "4:12", "text": "the range equation"}]}
    assert fact_binding_errors("She derives the range equation at 04:12.", [hit]) == []
    assert fact_binding_errors("She derives it at 4:12 and uses it at 6:40.", [hit]) == [
        "6:40 has no matching source metric"
    ]
    assert fact_binding_errors("She derives it at 04:12.", []) == ["4:12 has no matching source metric"]
    status = "cards due 12; exam in 19 days"
    assert fact_binding_errors("You have 12 cards due; the derivation is at 04:12.", [status, hit]) == []
    assert fact_binding_errors("You have 4 cards due at 4:12.", [status, hit])  # 4 is not the moment's 4


def test_a_timed_hit_carries_its_locator_and_moment_and_open_moment_resolves_to_it(tmp_path: Path) -> None:
    held = store(path=str(tmp_path / "learner.db"))  # the Study desk keeps its files beside the database
    desk = StudyDesk(held.conn, lambda: 0, Settings(study_workspace_enabled=True))
    source = video(desk)
    tools = tools_over(held)
    found = asyncio.run(tools.search({"query": "range equation"}, _Context()))  # type: ignore[arg-type]
    # Literal hits in order: the objective at 0:29 first, the derivation at 4:12 after it, each with its own moment.
    assert found["items"][0]["moment"] == "0:29" and found["items"][0]["locator"]["start_ms"] == 29_000
    item = next(i for i in found["items"] if i["moment"] == "4:12")
    assert item["locator"] == {"kind": "time", "start_ms": 252_000, "end_ms": 400_000}
    assert "substituting the time of flight gives the range equation" in item["text"]
    wire = json.dumps(found)
    assert source["source_id"] not in wire and "src_" not in wire  # integer refs, never a stored id
    chosen = resolve_action({"kind": "open_moment", "ref": item["ref"]}, tools.bands, tools.moments)
    assert chosen == {"action": "open_moment", "payload": {"source_id": source["source_id"], "at_ms": 252_000}}
    assert resolve_action({"kind": "open_moment", "ref": 64}, tools.bands, tools.moments) is None
    assert resolve_action({"kind": "open_moment", "ref": None}, tools.bands, tools.moments) is None
    event = action_event("open_moment", chosen["payload"])
    assert event["label_key"] == "study.companion.action.open_moment" and event["payload"]["at_ms"] == 252_000
    # Recall by code before the call carries the same: an excerpt's moment is its line's.
    tools.new_turn()
    by_code = tools.search_text("where does she derive the range equation")
    moments = {i["moment"]: i for i in by_code}
    assert {"0:29", "4:12"} <= set(moments)  # the objective that names it, and the derivation itself
    assert tools.moments[moments["4:12"]["ref"]] == (source["source_id"], 252_000)
    assert moments["4:12"]["text"].startswith("(4:12) substituting")  # one line, its moment beside it


def test_the_lines_within_thirty_seconds_of_a_moment_are_its_context(tmp_path: Path) -> None:
    held = store(path=str(tmp_path / "learner.db"))
    desk = StudyDesk(held.conn, lambda: 0, Settings(study_workspace_enabled=True))
    source = video(desk)
    tools = tools_over(held)
    title, items = tools.moment_lines(source["source_id"], 252_000)
    assert title == "Projectile motion"
    assert [i["moment"] for i in items] == ["3:50", "3:56", "4:03", "4:12", "4:21", "4:30"]
    assert all("[" not in i["text"] for i in items)  # the lines' words, their moments beside them
    assert all(tools.moments[i["ref"]][0] == source["source_id"] for i in items)
    # A private source gives its title only (STU-15).
    desk.patch(source["source_id"], {"private": True})
    assert tools.moment_lines(source["source_id"], 252_000) == ("Projectile motion", [])


def test_the_moment_fence_is_cut_for_a_cloud_call_without_study_materials_but_the_fact_stays() -> None:
    lines = ["[1] Projectile motion (at 4:12): substituting the time of flight gives the range equation"]
    user = "\n\n".join([records_fence([], lines), "About 4:12 in Projectile motion.", "<student>why sin 2θ?</student>"])
    without = strip_for_cloud(user, share_materials=False)
    assert "<own-materials>" not in without and "substituting" not in without
    assert "About 4:12 in Projectile motion." in without and "<student>why sin 2θ?</student>" in without
    with_materials = strip_for_cloud(user, share_materials=True)
    assert "substituting the time of flight" in with_materials and "About 4:12" in with_materials


def test_ask_about_this_moment_puts_the_lines_in_the_next_turn_only(tmp_path: Path) -> None:
    script = {"companion": [turn("Because the range depends on the sine of twice the angle, as she says at 4:12."),
                            turn("Keep going.")]}  # fmt: skip

    async def go() -> None:
        t = await thread(tmp_path, script)
        try:
            source = video(t.r.core.study.desk())
            body = {"context": {"source_id": source["source_id"], "at_ms": 252_000}}
            opened = await t.api.call("POST", "/v1/companion", body, profile=t.token)
            assert opened.status_code == 200, opened.text
            session_id = opened.json()["session_id"]
            await t.say(session_id, "Why does the range depend on sin 2θ?")
            first = _user(t.companion_requests()[0])
            assert "<own-materials>" in first and "(at 4:12): substituting the time of flight" in first
            assert "(at 3:50):" in first and "(at 4:30):" in first and "(at 6:40):" not in first  # ±30 s only
            assert "About 4:12 in Projectile motion." in first
            # The reply named the moment the context gave: the gate accepted it without a nudge.
            assert len(t.companion_requests()) == 1
            snap = await t.snapshot(session_id)
            assert [p["text"] for p in snap["parts"].values() if p.get("kind") == "text"][-1].startswith(
                "Because the range"
            )
            # The context was consumed: the next turn carries no moment.
            await t.say(session_id, "And the maximum height?")
            second = _user(t.companion_requests()[-1])
            assert "About 4:12" not in second and "(at 4:12)" not in second
            # A material that is not this profile's is refused before anything is kept.
            bad = await t.api.call("POST", "/v1/companion", {"context": {"source_id": "src_" + "0" * 26, "at_ms": 1}},
                                   profile=t.token)  # fmt: skip
            assert bad.status_code == 404
        finally:
            await stop_core(t.r)

    run(go())


NOT_YET = "Apply the equations of uniform acceleration to motion under gravity"  # the pack's free-fall statement


def _ready_outline(t: Thread) -> None:
    """A ready teaching outline on a lecture: two skills, the range secure and free fall not started."""
    desk = t.r.core.study.desk()
    source = video(desk)
    aid_id, job_id = "aid_" + new_ulid(), "stj_" + new_ulid()
    cite = [{"source_id": source["source_id"], "revision": 1, "chunk_id": "sck_" + "0" * 26, "start": 0,
             "end": 1, "quote": "x"}]  # fmt: skip
    outline = {
        "objectives": [], "examples": [], "assumes": [],
        "concepts": [
            {"name": "Range", "citations": cite, "at_ms": 252_000, "kc_ids": [RANGE], "outside_packs": False},
            {"name": "Time of flight", "citations": cite, "at_ms": 400_000, "kc_ids": [FLIGHT],
             "outside_packs": False},
        ],
        "skips": [], "for_you": [{"kc_id": RANGE, "band": "secure"}, {"kc_id": FLIGHT, "band": "not_started"}],
    }  # fmt: skip
    aid = {"aid_id": aid_id, "job_id": job_id, "kind": "teaching_outline", "title": "Projectile motion",
           "sources": [{"source_id": source["source_id"], "revision": 1}], "status": "ready",
           "created_at": "2026-10-31T10:00:00.000Z", "claims": [{"text": "Range", "citations": cite}],
           "outline": outline}  # fmt: skip
    desk.conn.execute("INSERT INTO study_aids VALUES (?,?,?)", (aid_id, json.dumps(aid), 1))
    desk.conn.execute("INSERT INTO study_aid_sources VALUES (?,?,?)", (aid_id, source["source_id"], 1))


def test_what_i_have_not_got_yet_is_a_code_fact_set_from_the_outline_and_the_learners_bands(tmp_path: Path) -> None:
    # The reply names the labelled counts the fact set carries: they bind, so the reply stands (fix 2026-11-01).
    script = {"companion": [turn("Of this video's 2 skills, 1 is not yet secure. Shall we start there?")]}

    async def go() -> None:
        t = await thread(tmp_path, script)
        try:
            _ready_outline(t)
            opened = await t.open()
            await t.say(opened["session_id"], "What does this video teach that I haven't got yet?")
            user = _user(t.companion_requests()[0])
            facts = json.loads(
                user.split("Verified facts (select fact_refs; code renders the statement and source): ")[1].split(
                    "\n\n"
                )[0]
            )
            outline_facts = [f for f in facts if f["source"] == "teaching outline"]
            # The skills not yet secure first, then the labelled counts: skills 2, not yet secure 1.
            assert [(f["value"], f["unit"]) for f in outline_facts] == [
                ("not_started", "band"), ("secure", "band"), (2, "skills"), (1, "skills")]  # fmt: skip
            assert outline_facts[0]["statement"].startswith(f"Recorded practice band for {NOT_YET}: not started")
            assert "Projectile motion teaches it at 6:40" in outline_facts[0]["statement"]
            assert [f["metric"] for f in outline_facts[2:]] == ["outline_skills", "outline_skills_not_yet_secure"]
            assert outline_facts[2]["statement"] == "Projectile motion teaches 2 skills."
            assert outline_facts[3]["statement"].endswith("not yet secure: 1 skills.")
            # The model selects a fact; code renders it: the words come from the record, never the model.
            engine_facts = t.r.core.sessions[opened["session_id"]].engine.companion.facts  # type: ignore[union-attr]
            rendered = companion_facts.selected_text(engine_facts, [outline_facts[0]["ref"]])
            assert "not started" in rendered and "not_started" not in rendered
            assert "teaching outline" in rendered and "6:40" in rendered
            snapshot = await t.snapshot(opened["session_id"])
            assert "Of this video's 2 skills, 1 is not yet secure." in json.dumps(snapshot)
            (trace,) = _companion_traces(t)
            assert trace["degraded_reason"] is None
            assert not any(g["fired"] for g in trace["gates"])
        finally:
            await stop_core(t.r)

    run(go())


def test_a_reply_refused_twice_with_an_outline_in_hand_falls_back_to_the_code_built_line(tmp_path: Path) -> None:
    """Live-run fix 2026-11-01: the model answered with an unlabelled number, fact binding exhausted its nudge, and
    the learner saw the canned line although the code fact set held the answer."""
    wrong = turn("There is 1 left for you: motion under gravity.")  # an unlabelled number, as in the live run
    script = {"companion": [wrong, wrong]}

    async def go() -> None:
        t = await thread(tmp_path, script)
        try:
            _ready_outline(t)
            opened = await t.open()
            await t.say(opened["session_id"], "What does this video teach that I haven't got yet?")
            said = json.dumps(await t.snapshot(opened["session_id"]))
            assert f"Of this video's 2 skills, 1 is not yet secure: {NOT_YET}." in said
            assert "couldn't put that together" not in said and "1 left for you" not in said
            (trace,) = _companion_traces(t)
            gates = {g["gate"]: g for g in trace["gates"]}
            assert (gates["fact_binding"]["fired"], gates["fact_binding"]["outcome"],
                    gates["fact_binding"]["detail"]) == (True, "exhausted_canned", "number:1:unit:none")  # fmt: skip
            assert trace["degraded_reason"] == "companion_canned"  # still a refused reply, said honestly
        finally:
            await stop_core(t.r)

    run(go())


def test_the_outline_line_names_at_most_six_skills_and_the_counts() -> None:
    from agent_core.engine.companion import OutlineFacts, outline_line
    from agent_core.engine.companion_opener import load_templates

    templates = load_templates()
    many = OutlineFacts("Projectile motion", 9, [f"Skill {i}" for i in range(8)], [])
    line = outline_line(templates, many)
    assert line is not None and line.startswith("Of this video's 9 skills, 8 are not yet secure: Skill 0; Skill 1;")
    assert line.endswith("Skill 5.") and "Skill 6" not in line
    assert (
        outline_line(templates, OutlineFacts("x", 3, [], [])) == "All 3 skills this video teaches are secure for you."
    )
    assert outline_line(templates, OutlineFacts("x", 0, [], [])) is None


def test_a_reply_refused_twice_with_only_progress_read_falls_back_to_the_bands_in_words(tmp_path: Path) -> None:
    """Live-run fix 2026-11-01 (second pass): "What haven't I got yet?" before any lecture ended in the canned line
    (fact binding, `number:1:unit:none`, `exhausted_canned`) though `progress_read` had given the bands. The line is
    now built by code from those facts, bands in words, each with its source, and never shows a band's code."""
    from w8_companion_harness import calls

    wrong = turn("There is 1 left for you: motion under gravity.")
    script = {"companion": [calls(("progress_read", {})), wrong, wrong]}

    async def go() -> None:
        t = await thread(tmp_path, script)
        try:
            conn = t.r.core.records.learner.conn  # type: ignore[union-attr]
            for kc, status, p, checked in ((FLIGHT, "learning", 0.4, "none"), (RANGE, "mastered", 0.97, "passed")):
                conn.execute(
                    "INSERT INTO kc_mastery (kc_id, status, p_mastery, n_eff, attempts, correct, mastery_check_state,"
                    " last_seen_at, last_event_seq) VALUES (?, ?, ?, 6, 6, 5, ?, 1, 1)",
                    (kc, status, p, checked),
                )
            opened = await t.open()
            await t.say(opened["session_id"], "What haven't I got yet?")
            snapshot = await t.snapshot(opened["session_id"])
            said = " ".join(p.get("text", "") for p in snapshot["parts"].values() if p.get("kind") == "text")
            assert "where your checked practice records stand" in said
            assert f"Recorded practice band for {NOT_YET}: learning." in said and ": secure." in said
            assert said.index(": learning.") < said.index(": secure.")  # not yet secure first
            assert "Source: checked practice records (" in said
            assert (
                "not_started" not in said and "couldn't put that together" not in said and "1 left for you" not in said
            )
            assert said.count("Recorded practice band for ") <= 6
            assert [a["action"] for a in snapshot["actions"].values()] == ["open_knows"]  # "See what your tutor knows"
            (trace,) = _companion_traces(t)
            gates = {g["gate"]: g for g in trace["gates"]}
            assert (gates["fact_binding"]["outcome"], gates["fact_binding"]["detail"]) == (
                "exhausted_canned", "number:1:unit:none")  # fmt: skip
            assert trace["degraded_reason"] == "companion_canned"
        finally:
            await stop_core(t.r)

    run(go())


def test_the_progress_line_puts_skills_not_yet_secure_first_names_six_and_says_bands_in_words() -> None:
    from agent_core.engine.companion import progress_line
    from agent_core.engine.companion_opener import load_templates

    facts = companion_facts.from_progress(
        {"bands": [{"ref": i, "skill": f"Skill {i}", "band": band} for i, band in
                   enumerate(["secure", "learning", "not_started", "secure", "not_started", "learning", "secure",
                              "not_started", "learning", "not_started"], 1)]},
        period="2026-11-01")  # fmt: skip
    line, refs = progress_line(load_templates(), facts)  # type: ignore[misc]
    assert len(refs) == 6 and all(facts[r - 1].value != "secure" for r in refs)  # six of the seven not yet secure
    assert "Skill 2: learning." in line and "Skill 3: not started." in line and "Skill 1:" not in line
    assert "not_started" not in line and line.count("Source: checked practice records (2026-11-01).") == 6
    assert progress_line(load_templates(), []) is None
    assert (
        progress_line(load_templates(), [companion_facts.Fact("a", "due_cards", 2, "cards", "x", "p", "s", "t")])
        is None
    )


EXPLAIN = (
    "The range equation has sin two theta in it, and sin two theta is greatest when two theta is ninety "
    "degrees, which is at forty five degrees, as she says at 4:30."
)


def test_ask_about_this_moment_may_explain_from_the_lines_it_was_given(tmp_path: Path) -> None:
    """Live-run fix 2026-11-01: "Why does the range depend on sin two theta?" at 4:12 was answered with an offer to
    open the video. An explanation from the cited lines says "two", "ninety" and "forty five", figures that are the
    lecture's own words, and fact binding refused each (`number:2:unit:none`), so the reply was nudged into saying
    nothing. A figure the given lines say, with no unit of progress beside it, binds to them."""
    script = {"companion": [turn(EXPLAIN)]}

    async def go() -> None:
        t = await thread(tmp_path, script)
        try:
            source = video(t.r.core.study.desk())
            body = {"context": {"source_id": source["source_id"], "at_ms": 252_000}}
            opened = await t.api.call("POST", "/v1/companion", body, profile=t.token)
            session_id = opened.json()["session_id"]
            await t.say(session_id, "Why does the range depend on sin two theta?")
            assert len(t.companion_requests()) == 1  # accepted at once: no nudge, no second pass
            # The role tells the model to explain from the lines, not to offer the video instead.
            assert "never offering the video instead" in json.dumps(
                t.companion_requests()[0]["messages"][0])  # fmt: skip
            snapshot = await t.snapshot(session_id)
            said = [p["text"] for p in snapshot["parts"].values() if p.get("kind") == "text"][-1]
            assert said == EXPLAIN
            (trace,) = _companion_traces(t)
            assert not any(g["fired"] for g in trace["gates"]) and trace["degraded_reason"] is None
            assert not snapshot.get("actions")  # it explained; it did not send them away
        finally:
            await stop_core(t.r)

    run(go())


def test_a_figure_the_lecture_did_not_say_still_fails_fact_binding_and_a_unit_still_needs_its_source() -> None:
    lines = ["[1] Projectile motion (at 4:30): and the range is greatest when two theta is ninety degrees"]
    said = companion_facts.figures(lines)
    assert said == {"2", "90", "4:30"}
    assert fact_binding_errors("It peaks when two theta is ninety degrees.", [], said) == []
    assert fact_binding_errors("It peaks at seventy degrees.", [], said) == ["70 has no matching source metric"]
    # A figure the lines say, but beside a progress unit, is still a progress claim that needs a source.
    assert fact_binding_errors("You have 90 cards due.", [], said) == ["90 has no matching source metric"]
    assert fact_binding_errors("It peaks at 90.", [], frozenset()) == ["90 has no matching source metric"]
    assert fact_binding_errors("She says it at 04:30.", [], said) == []  # a moment the given lines carry
    assert fact_binding_errors("She says it at 6:40.", [], said) == ["6:40 has no matching source metric"]
