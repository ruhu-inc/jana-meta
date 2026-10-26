"""The concept map over the local API (UXS-22 map view): the pack's skill backbone with the learner's states, the
root-gap links (never shown as reviewed when no reviewer is named), the ranked what next, the gap path, and the
learner's questions and mistakes attached to the KCs the engine assigned, without any model call.

Against the real core with development-signed packs of the repository's Physics and Maths sources; replies are
validated against the command contract. Every learner is synthetic. The renderer's layout tests read the backbone
written here (`packages/renderers/fixtures/concept-map/*.json`) and the UI's tests the whole Physics reply with the
synthetic questions (`packages/ui/test/fixtures/concept-map.phy.json`): set JANA_WRITE_CONCEPT_FIXTURES=1 to rewrite
them."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from agent_core.engine.concept_map import gap_path, what_next
from agent_core.store.sqlite import transaction
from api_harness import start_core, stop_core
from jana_tools import REPO_ROOT
from test_m13g_learn import SETTINGS, Client, install, mastery, run, source

FIXTURES = REPO_ROOT / "packages" / "renderers" / "fixtures" / "concept-map"
# The whole Physics reply with this file's synthetic questions and mistakes: the UI's concept-map tests read it.
UI_FIXTURE = REPO_ROOT / "packages" / "ui" / "test" / "fixtures" / "concept-map.phy.json"
V_T = "kc.phy.o.motion.velocity_time_gradient"
GRADIENT = "kc.mth.o.coordinate_geometry.gradient"
SINGLE_POINT = "mc.phy.o.vt_gradient_from_one_point"
SPEED = "kc.phy.o.motion.average_speed"


def kcs_of(subject: str) -> list[dict[str, Any]]:
    return [k for k in source(subject)["kcs"] if k.get("status", "active") == "active"]


def session(conn: Any, session_id: str, subject: str | None, *, purged: int | None = None) -> None:
    conn.execute("INSERT INTO sessions (session_id, mode, subject, started_at, transcript_purged_at)"
                 " VALUES (?, 'guided', ?, 1000, ?)", (session_id, subject, purged))  # fmt: skip


def turn(conn: Any, session_id: str, idx: int, text: str | None, kind: str = "typed", at: int = 2000) -> str:
    student, tutor = f"msg_{session_id}_{idx}", f"trn_{session_id}_{idx}"
    conn.execute("INSERT INTO turns (turn_id, session_id, idx, speaker, status, student_text, input_kind, started_at)"
                 " VALUES (?, ?, ?, 'student', 'complete', ?, ?, ?)", (student, session_id, idx, text, kind, at))  # fmt: skip
    conn.execute("INSERT INTO turns (turn_id, session_id, idx, speaker, status, started_at)"
                 " VALUES (?, ?, ?, 'tutor', 'complete', ?)", (tutor, session_id, idx + 1, at))  # fmt: skip
    return tutor


def event(conn: Any, kind: str, session_id: str, turn_id: str | None, kc_ids: list[Any]) -> None:
    n = conn.execute("SELECT coalesce(max(seq), 0) + 1 FROM events").fetchone()[0]
    conn.execute("INSERT INTO events (event_id, profile_id, device_id, origin_seq, hlc, type, schema_version, source,"
                 " sync_class, occurred_at, recorded_at, session_id, turn_id, kc_ids, payload) VALUES"
                 " (?, 'pro_test', 'dev_test', ?, ?, ?, '1.0.0', 'engine', 'local', 3000, 3000, ?, ?, ?, '{}')",
                 (f"evt_{n}", n, f"{n:016d}", kind, session_id, turn_id, json.dumps(kc_ids)))  # fmt: skip


def misconception(conn: Any, mc_id: str, kc_id: str, status: str = "active", count: int = 2) -> None:
    conn.execute("INSERT INTO learner_misconceptions (misconception_id, kc_id, status, evidence_count, first_seen_at,"
                 " last_seen_at, last_event_seq) VALUES (?, ?, ?, ?, 10, 20, 0)", (mc_id, kc_id, status, count))  # fmt: skip


def explaining(conn: Any, kc_id: str) -> None:
    body = {"assessment_id": "asm_x", "kind": "mastery_check", "state": "explaining", "kc_id": kc_id}
    conn.execute("INSERT INTO assessment_runs (assessment_id, kind, state, body, updated_at)"
                 " VALUES ('asm_x', 'mastery_check', 'in_progress', ?, 1)", (json.dumps(body),))  # fmt: skip


def fixture(reply: dict[str, Any]) -> dict[str, Any]:
    """What the renderer's layout reads: each node's id, code and whether it is linked, and each edge."""
    return {"subject_id": reply["subject_id"],
            "nodes": [{"id": n["kc_id"], "code": n["code"], "linked": n["linked"]} for n in reply["nodes"]],
            "edges": [{"from": e["from"], "to": e["to"], "kind": e["kind"]} for e in reply["edges"]]}  # fmt: skip


def test_backbone_nodes_edges_states_and_root_gaps(tmp_path: Path) -> None:
    async def scenario() -> None:
        install(tmp_path, "phy")
        install(tmp_path, "mth")
        r = await start_core(tmp_path, settings=SETTINGS, worker=False)
        try:
            c = Client(r)
            for subject in ("phy", "mth"):
                reply = await c.ok("GET", f"/v1/curriculum/cur.{subject}.o/concept-map", definition="ConceptMap")
                assert reply["status"] == "ready" and reply["pack"] == {"pack_id": f"pack.{subject}.o", "version": "0.1.0"}
                own = [n for n in reply["nodes"] if not n["linked"]]
                assert {n["kc_id"] for n in own} == {k["id"] for k in kcs_of(subject)}
                prerequisites = sum(len(k.get("prerequisites") or []) for k in kcs_of(subject))
                assert len([e for e in reply["edges"] if e["kind"] == "prerequisite"]) == prerequisites
                ids = {n["kc_id"] for n in reply["nodes"]}
                assert all(e["from"] in ids and e["to"] in ids for e in reply["edges"]), "every edge has both ends"
                assert {n["state"] for n in reply["nodes"]} == {"not_started"}
                path = FIXTURES / f"{subject}.json"
                if os.environ.get("JANA_WRITE_CONCEPT_FIXTURES"):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps(fixture(reply), indent=1) + "\n")
                assert json.loads(path.read_text()) == fixture(reply), "renderer fixture is stale"
            physics = await c.ok("GET", "/v1/curriculum/cur.phy.o/concept-map", definition="ConceptMap")
            gaps = [e for e in physics["edges"] if e["kind"] == "root_gap"]
            # The ten Physics root gaps reach Maths KCs, which join the map as linked nodes; none names a reviewer.
            assert len({e["misconception_id"] for e in gaps}) == 10
            assert all(e["from"].startswith("kc.mth.") and e["reviewed"] is False for e in gaps)
            linked = {n["kc_id"] for n in physics["nodes"] if n["linked"]}
            assert linked == {e["from"] for e in gaps}
            (single,) = [e for e in gaps if e["misconception_id"] == SINGLE_POINT]
            assert (single["from"], single["to"], single["idea"]) == (GRADIENT, V_T, "the gradient of a straight line")
            # The Maths map shows the same links from its side, with the Physics KCs linked.
            maths = await c.ok("GET", "/v1/curriculum/cur.mth.o/concept-map", definition="ConceptMap")
            assert {e["misconception_id"] for e in maths["edges"] if e["kind"] == "root_gap"} == {
                e["misconception_id"] for e in gaps}
            assert all(n["kc_id"].startswith("kc.phy.") for n in maths["nodes"] if n["linked"])

            conn = r.runtime.learner.conn
            mastery(r, SPEED, "mastered")
            with transaction(conn):
                explaining(conn, V_T)
            moved = await c.ok("GET", "/v1/curriculum/cur.phy.o/concept-map", definition="ConceptMap")
            states = {n["kc_id"]: (n["state"], n["band"]) for n in moved["nodes"]}
            assert states[SPEED] == ("mastered", "secure") and states[V_T] == ("explaining", "learning")
            assert "p_mastery" not in json.dumps(moved), "no probability reaches the map"

            for bad in ("cur.phy", "cur.xyz.o", "cur.phy.o.motion_forces_and_energy"):
                assert (await c.get(f"/v1/curriculum/{bad}/concept-map")).status_code == 404
            missing = await c.ok("GET", "/v1/curriculum/cur.chm.o/concept-map", definition="ConceptMap")
            assert missing["status"] == "not_installed" and missing["nodes"] == [] and missing["pack"] is None
        finally:
            await stop_core(r)

    run(scenario())


def test_what_next_ranks_ready_high_value_first() -> None:
    kcs = {
        "kc.phy.o.t.a": {"code": "A", "exam_weight": 0.2, "prerequisites": []},
        "kc.phy.o.t.b": {"code": "B", "exam_weight": 0.9, "prerequisites": [{"kc_id": "kc.phy.o.t.a", "strength": "required"}]},
        "kc.phy.o.t.c": {"code": "C", "exam_weight": 0.6, "prerequisites": [{"kc_id": "kc.phy.o.t.d", "strength": "helpful"}]},
        "kc.phy.o.t.d": {"code": "D", "exam_weight": 0.3, "prerequisites": []},
        "kc.phy.o.t.e": {"code": "E", "exam_weight": 1.0, "prerequisites": []},
    }
    states = {"kc.phy.o.t.e": "mastered"}
    ranked = what_next(kcs, states, {"kc.phy.o.t.d": 0.9})
    # C is ready (a helpful prerequisite never blocks), A and D need nothing; B waits for A; E is secure.
    assert [(n["kc_id"][-1], n["reason"], n["weight"]) for n in ranked] == [
        ("c", "ready", "high"), ("a", "foundation", "low"), ("d", "foundation", "medium"), ("b", "needs_first", "high")]
    assert ranked[-1]["needs"] == ["kc.phy.o.t.a"]
    assert ranked[1]["kc_id"] == "kc.phy.o.t.a", "D's high P puts it below A despite its weight"
    states["kc.phy.o.t.a"] = "needs_review"
    assert what_next(kcs, states, {})[0] == {"kc_id": "kc.phy.o.t.b", "reason": "ready", "weight": "high", "needs": []}


def test_gap_path_is_the_shortest_chain_and_stable() -> None:
    edges = [{"from": "m", "to": "p"}, {"from": "m", "to": "x"}, {"from": "x", "to": "y"}, {"from": "y", "to": "q"},
             {"from": "p", "to": "q"}, {"from": "a", "to": "b"}]
    assert gap_path(edges, "m", "q") == ["m", "p", "q"]
    assert gap_path(edges, "m", "m") == ["m"]
    assert gap_path(edges, "q", "m") == [] and gap_path(edges, "m", "b") == []


def test_questions_and_mistakes_attach_to_the_engines_kcs(tmp_path: Path) -> None:
    async def scenario() -> None:
        install(tmp_path, "phy")
        install(tmp_path, "mth")
        r = await start_core(tmp_path, settings=SETTINGS, worker=False)
        try:
            c = Client(r)
            conn = r.runtime.learner.conn
            with transaction(conn):
                # Three sessions on the v-t gradient: the answering turn's attempt names it (objects, as attempts
                # store them), a hint names it on a later turn, and a spoken question's session names it most.
                for n, kind in ((1, "typed"), (2, "typed"), (3, "voice")):
                    sid = f"s{n}"
                    session(conn, sid, "physics")
                    tutor = turn(conn, sid, 0, f"How do I get acceleration from this graph {n}?", kind, at=2000 + n)
                    if n == 1:
                        event(conn, "attempt", sid, tutor, [{"kc_id": V_T, "weight": 1.0}])
                    else:
                        later = turn(conn, sid, 2, "ok", at=2100)
                        event(conn, "hint", sid, later, [V_T])
                        event(conn, "hint", sid, later, [SPEED])
                        event(conn, "hint", sid, later, [V_T])
                    turn(conn, sid, 4, "thanks", at=2200)  # not a question: neither first nor asking
                # A card answer is never a question; a follow-up with "?" is.
                tutor = turn(conn, "s1", 6, "Why is it the change?", at=2300)
                event(conn, "verdict", "s1", tutor, [SPEED])
                conn.execute("UPDATE turns SET input_kind = 'card_answer' WHERE turn_id = 'msg_s2_4'")
                # A photographed question with no KC: an open question of the subject.
                session(conn, "s4", "physics")
                turn(conn, "s4", 0, "What does this circuit symbol mean?", at=2400)
                conn.execute("INSERT INTO captures (capture_id, session_id, record, expires_at) VALUES"
                             " ('cap_01HZZZZZZZZZZZZZZZZZZZZZZZ', 's4', ?, 99999999)", (json.dumps({"source": "photo_file", "purpose": "question"}),))
                # A Maths session with no KC is not on the Physics map; a purged session keeps its count, no words.
                session(conn, "s5", "mathematics")
                turn(conn, "s5", 0, "What is a prime?", at=2500)
                session(conn, "s6", "physics", purged=5000)
                event(conn, "attempt", "s6", None, [{"kc_id": V_T, "weight": 1.0}])
                misconception(conn, SINGLE_POINT, V_T, "active", 3)
                misconception(conn, "mc.phy.o.speed_from_distance_only", SPEED, "resolved", 1)
                misconception(conn, "mc.phy.o.gradient_axes_swapped", V_T, "disputed", 1)
            reply = await c.ok("GET", "/v1/curriculum/cur.phy.o/concept-map", definition="ConceptMap")
            asked = reply["questions"]
            on = [q for q in asked if q["kc_id"] == V_T]
            assert len(on) == 4, asked  # three sessions with words and the purged one without
            assert {q["input"] for q in on if q["kept"]} == {"typed", "spoken"}
            (purged,) = [q for q in on if not q["kept"]]
            assert purged["text"] is None and purged["session_id"] == "ses_s6"
            assert [q["text"] for q in asked if q["kc_id"] == SPEED] == ["Why is it the change?"]
            (open_q,) = [q for q in asked if q["kc_id"] is None]
            assert open_q["text"] == "What does this circuit symbol mean?" and open_q["input"] == "photo"
            texts = {q["text"] for q in asked}
            assert not texts & {"ok", "thanks", "What is a prime?"}
            assert [q["asked_at"] for q in asked] == sorted((q["asked_at"] for q in asked), reverse=True)

            mistakes = reply["mistakes"]
            # Most seen first, a resolved one last, a disputed one never.
            assert [m["misconception_id"] for m in mistakes] == [SINGLE_POINT, "mc.phy.o.speed_from_distance_only"]
            single = mistakes[0]
            assert (single["name"], single["times"], single["status"]) == ("Acceleration from a single point", 3, "active")
            assert single["root_kc_id"] == GRADIENT and single["reviewed"] is False
            assert single["gap_path"] == [GRADIENT, V_T]
            assert single["idea"] == "the gradient of a straight line"
            if os.environ.get("JANA_WRITE_CONCEPT_FIXTURES"):
                UI_FIXTURE.parent.mkdir(parents=True, exist_ok=True)
                UI_FIXTURE.write_text(json.dumps(reply, indent=1, ensure_ascii=False) + "\n")
            assert json.loads(UI_FIXTURE.read_text()) == reply, "UI fixture is stale"
        finally:
            await stop_core(r)

    run(scenario())
