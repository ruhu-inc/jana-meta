"""A profile archive carries companion state, respects transcript authorization, and preserves forget boundaries."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from agent_core.engine.companion_history import record_context
from agent_core.engine.companion_opener import Facts
from agent_core.memory.visibility import advance, revision
from agent_core.memory.write import summary_body
from agent_core.store.exports import build_profile_archive, read_profile_archive
from agent_core.store.migration_v9 import LEARNER
from agent_core.store.sqlite import transaction
from memory_harness import store


def test_companion_archive_carries_context_revision_and_only_authorized_history(tmp_path: Path) -> None:
    held = store()
    held.conn.executescript(LEARNER)
    sid = held.session("A" * 26)
    thread = "cth_" + "B" * 26
    opener = {
        "opener_id": "2026-10-09",
        "text": "Ready to study?",
        "facts": Facts(None, None, None, 0, None, False, "2026-10-09").view(),
    }
    held.conn.execute(
        "INSERT INTO companion_episodes VALUES (?, ?, '2026-10-09', ?, 1, NULL, NULL)",
        (sid, thread, json.dumps(opener)),
    )
    held.conn.execute("INSERT INTO companion_summary VALUES (?,0,0,1,?)", (thread, json.dumps(summary_body())))
    held.conn.execute(
        "INSERT INTO turns (turn_id,session_id,idx,speaker,status,student_text,started_at)"
        " VALUES ('request',?,0,'student','complete','private old preference',1)",
        (sid,),
    )
    record_context(held.conn, "request", "companion", {})
    with transaction(held.conn):
        advance(held.conn, held.clock.now)
    included = read_profile_archive(
        build_profile_archive(held.conn, tmp_path, "test", "2026-10-09T12:00:00Z", [sid], False)
    )
    assert included.companion["revision"]["id"] == revision(held.conn)
    assert included.companion["episodes"][0]["thread_id"] == thread
    assert included.companion["turn_context"][0]["turn_id"] == "request"
    excluded = read_profile_archive(
        build_profile_archive(held.conn, tmp_path, "test", "2026-10-09T12:00:00Z", [], False)
    )
    assert excluded.companion["turn_context"] == []
    assert excluded.sessions == {}


def test_import_of_an_older_archive_does_not_revive_locally_forgotten_memory(tmp_path: Path) -> None:
    from agent_core.memory.write import correct_preference, forget
    from learner_harness import Clock
    from memory_harness import Store
    from test_m10a_profiles import student
    from test_m10d_deletion_export import PASSPHRASE, _export, _with_exports

    async def scenario(api, runtime):
        profile = await api.add(student("Ama"))
        token = (await api.unlock(profile)).json()["profile_token"]
        # Opening the thread binds the learner service without requiring any model inference.
        opened = await api.call("POST", "/v1/companion", {}, profile=token)
        assert opened.status_code == 200, opened.text
        learner = runtime.core.records.learner
        held = Store(learner, Clock(runtime.core.clock_ms()), profile[4:])
        note_id = held.note("Prefers drawing labelled force diagrams", opened.json()["session_id"])
        assert correct_preference(learner, "start_style", "worked_example", "student")
        response, archive = await _export(
            api, token, tmp_path / "archive", kind="profile_archive", profile_ids=[profile], passphrase=PASSPHRASE
        )
        assert response.status_code == 202
        assert forget(learner, note_id, "student") is not None
        assert correct_preference(learner, "start_style", None, "student")
        imported = await api.call(
            "POST",
            "/v1/profiles/import",
            {
                "source": {"kind": "file", "path": str(archive)},
                "passphrase": PASSPHRASE,
            },
        )
        assert imported.status_code == 202, imported.text
        job = (await api.call("GET", "/v1/jobs/" + imported.json()["job_id"])).json()
        with runtime.runtime.directory.open_learner(job["result_ref"]) as conn:
            assert conn.execute("SELECT count(*) FROM notes WHERE status='active'").fetchone()[0] == 0
            assert conn.execute("SELECT count(*) FROM preferences").fetchone()[0] == 0
            assert revision(conn)

    _with_exports(tmp_path, scenario)


def test_restore_does_not_reuse_source_database_sequence_numbers() -> None:
    from agent_core.store.companion_archive import restore, snapshot

    original, restored = store(), store()
    thread = "cth_" + "B" * 26
    body = {**summary_body(), "cursor_seq": 900, "version": 4}
    original.conn.execute("INSERT INTO companion_summary VALUES (?,4,900,1,?)", (thread, json.dumps(body)))
    with transaction(restored.conn):
        restore(restored.conn, snapshot(original.conn, []))
    assert restored.conn.execute("SELECT cursor_seq FROM companion_summary").fetchone()[0] == 0


@pytest.mark.parametrize("corruption", ["unknown_session", "unknown_turn", "invalid_policy", "unknown_column"])
def test_companion_archive_rejects_invalid_provenance(corruption: str) -> None:
    from agent_core.store.companion_archive import snapshot, validate
    from agent_core.store.exports import ExportError

    held = store()
    rows = snapshot(held.conn, [])
    sessions = {"known": {"turns": [{"turn_id": "turn", "session_id": "known"}]}}
    if corruption == "unknown_session":
        sessions["known"]["turns"][0]["session_id"] = "another-profile-session"
    else:
        context = {"turn_id": "turn", "memory_revision": "", "kind": "companion", "egress_json": "{}"}
        if corruption == "unknown_turn":
            context["turn_id"] = "another-profile-turn"
        elif corruption == "invalid_policy":
            context["egress_json"] = '{"local_only":"false"}'
        else:
            context["unexpected"] = "unvalidated data"
        rows["turn_context"] = [context]
    with pytest.raises(ExportError, match="invalid companion state"):
        validate(rows, sessions)
