"""Multi-day acceptance: real API/storage/marker, scripted language model, deterministic advancing clock."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from agent_core.store.ids import new_ulid
from engine_harness import reply
from learner_harness import Clock
from memory_harness import PACK, SPEED, Store
from test_m10a_profiles import student
from test_m10d_deletion_export import PASSPHRASE, _export
from test_m24_remark import answer, item
from w8_companion_harness import calls, reopen, run, stop_core, thread, turn


def test_multi_day_personal_learning_agent_journey(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def select_practice_fact(body: dict[str, Any]) -> dict[str, Any]:
        supplied = body["messages"][-1]["content"]
        prefix = "Verified facts (select fact_refs; code renders the statement and source): "
        assert supplied.startswith(prefix)
        facts = json.loads(supplied.removeprefix(prefix))
        practice = next(fact for fact in facts if fact["metric"] == "skill_band")
        return reply(json.dumps({"text": "What would you like to practise?", "action": None,
                                 "fact_refs": [practice["ref"]]}))  # fmt: skip

    async def go() -> None:
        t = await thread(tmp_path, {"companion": [turn("We can return to the momentum example next time.")]})
        clock = Clock(t.r.core.clock_ms())

        def set_clock() -> None:
            t.r.core.clock_ms = clock
            t.r.core.companion.clock = clock
            t.r.core.records.learner.log.clock.wall_ms = clock

        try:
            set_clock()
            profile = t.r.runtime.directory.profile_of(t.token)
            opened = await t.open()
            await t.say(opened["session_id"], "Remember that I prefer a worked example before practice.")
            await t.say(opened["session_id"], "Remember that I prefer short explanations.")
            await t.say(opened["session_id"], "Next time, continue our momentum example.")
            visit = await t.api.call("POST", "/v1/study/session", {}, profile=t.token)
            assert visit.status_code == 200, visit.text
            source = await t.api.call(
                "POST",
                "/v1/study/sources",
                {
                    "kind": "text",
                    "title": "Momentum notes",
                    "text": "Momentum equals mass multiplied by velocity.",
                },
                profile=t.token,
            )
            assert source.status_code == 201, source.text
            await t.api.call("DELETE", "/v1/study/session", profile=t.token)
            clock.now += 86_400_000
            t = await reopen(t, {"companion": [turn("Let us continue the example.")]})
            set_clock()
            returned = await t.open()
            assert returned["thread_id"] == opened["thread_id"]
            assert returned["session_id"] != opened["session_id"]
            await t.say(returned["session_id"], "What did we agree to continue?")
            prompt = json.dumps(t.companion_requests()[-1]["messages"])
            assert "momentum example" in prompt and "worked_example" in prompt

            # Supply a published synthetic MCQ bank through the content dependency; selection, response validation,
            # deterministic marking and persistence all run through the same HTTP routes as the learner's app.
            learner = t.r.core.records.learner
            held = Store(learner, clock, profile[4:])
            bank = deepcopy(PACK)
            questions = [item(f"itm.phy.o.motion.{9990 + n}", "a") for n in range(4)]
            for question in questions:
                question["kc_ids"] = [SPEED]
            # Keep enough questions for the app's real mock reserve instead of disabling that selection policy.
            bank.records["items"] = {q["id"]: q for q in questions}
            bank.items = {q["id"]: 0.0 for q in questions}
            with monkeypatch.context() as patch:
                patch.setattr(t.r.runtime, "content", lambda: bank)
                desk = t.r.runtime.assessments()
                assert desk is not None
                desk.clock_ms = clock
                practice = await t.api.call(
                    "POST",
                    "/v1/practice/sets",
                    {
                        "client_set_id": "cli_" + new_ulid(),
                        "subject": "physics",
                        "size": 1,
                        "source": "topic",
                        "kc_ids": [SPEED],
                    },
                    profile=t.token,
                )
                assert practice.status_code == 200, practice.text
                chosen = practice.json()
                item_id = chosen["current_item"]["item_id"]
                assert item_id in bank.records["items"]
                marked = await t.api.call(
                    "POST",
                    f"/v1/practice/sets/{chosen['set_id']}/answers",
                    {
                        "client_attempt_id": "cli_" + new_ulid(),
                        "item_id": item_id,
                        "answer": answer("a"),
                        "time_ms": 30000,
                        "hints_used": 0,
                    },
                    profile=t.token,
                )
                assert marked.status_code == 200, marked.text
                assert marked.json()["verdict"] == "correct"
            sid = chosen["set_id"].removeprefix("set_")
            attempt_id = marked.json()["attempt_id"].removeprefix("att_")
            assert held.conn.execute("SELECT outcome FROM attempts WHERE attempt_id=?", (attempt_id,)).fetchone() == (
                "correct",
            )
            note_id = held.note("Prefers drawing labelled force diagrams", sid)
            knows = await t.api.call("GET", f"/v1/profiles/{profile}/knows", profile=t.token)
            assert knows.status_code == 200, knows.text
            assert knows.json()["notes"][0]["explanation"]["sources"]
            await t.say(returned["session_id"], "Actually, I prefer a hint first.")
            await t.say(returned["session_id"], "Forget my preference for short explanations.")
            await t.say(returned["session_id"], "Forget mem_" + note_id)
            clock.now += 86_400_000
            t = await reopen(t, {"companion": [calls(("progress_read", {})), select_practice_fact]})
            set_clock()
            third = await t.open()
            sessions = [
                "ses_" + r[0]
                for r in t.r.core.records.learner.conn.execute("SELECT session_id FROM companion_episodes")
            ]
            grant = await t.api.call(
                "POST",
                f"/v1/profiles/{profile}/archive-authorizations",
                {
                    "session_ids": sessions,
                    "include_attachments": False,
                    "confirmed": True,
                },
                profile=t.token,
            )
            assert grant.status_code == 200, grant.text
            exported, archive = await _export(
                t.api,
                t.token,
                tmp_path / "archive",
                kind="profile_archive",
                profile_ids=[profile],
                passphrase=PASSPHRASE,
                include_transcripts=True,
                include_study_sources=True,
                archive_authorization_id=grant.json()["authorization_id"],
            )
            assert exported.status_code == 202, exported.text
            imported = await t.api.call(
                "POST",
                "/v1/profiles/import",
                {
                    "source": {"kind": "file", "path": str(archive)},
                    "passphrase": PASSPHRASE,
                },
            )
            assert imported.status_code == 202, imported.text
            job = (await t.api.call("GET", "/v1/jobs/" + imported.json()["job_id"])).json()
            restored = job["result_ref"]
            t.token = (await t.api.unlock(restored)).json()["profile_token"]
            set_clock()
            resumed = await t.open()
            assert resumed["session_id"] == third["session_id"]
            await t.say(resumed["session_id"], "What should I practise?")
            after = json.dumps(t.companion_requests()[-1]["messages"])
            assert "prefers to start with hint" in after
            assert "worked_example" not in after and "labelled force diagrams" not in after
            shown = await t.snapshot(resumed["session_id"])
            wording = " ".join(part.get("text", "") for part in shown["parts"].values())
            today = datetime.fromtimestamp(clock.now / 1000, UTC).date().isoformat()
            assert "Recorded practice band for " in wording
            assert f"Source: checked practice records ({today})." in wording
            history = await t.api.call("GET", "/v1/companion/history", profile=t.token)
            assert any("momentum example" in row["text"] for row in history.json()["items"])
            conn = t.r.core.records.learner.conn
            assert conn.execute("SELECT count(*) FROM preferences").fetchone()[0] == 1
            assert conn.execute("SELECT count(*) FROM notes WHERE status='active'").fetchone()[0] == 0
            assert conn.execute("SELECT count(*) FROM attempts WHERE outcome='correct'").fetchone()[0] == 1
            assert conn.execute("SELECT count(*) FROM consents WHERE withdrawn_at IS NULL").fetchone()[0] == 0
            other = await t.api.add(student("Kofi"))
            t.token = (await t.api.unlock(other)).json()["profile_token"]
            await t.open()
            assert (await t.api.call("GET", "/v1/companion/history", profile=t.token)).json()["items"] == []
            assert t.r.core.records.learner.conn.execute("SELECT count(*) FROM preferences").fetchone()[0] == 0
            denied = await t.api.call("GET", f"/v1/profiles/{restored}/knows", profile=t.token)
            assert denied.status_code in (401, 403, 404)
            t.token = (await t.api.unlock(restored)).json()["profile_token"]
            back = await t.open()
            assert back["thread_id"] == resumed["thread_id"]
            returned_history = await t.api.call("GET", "/v1/companion/history", profile=t.token)
            assert any("momentum example" in row["text"] for row in returned_history.json()["items"])
            assert t.r.core.records.learner.conn.execute("SELECT count(*) FROM preferences").fetchone()[0] == 1
        finally:
            await stop_core(t.r)

    run(go())
