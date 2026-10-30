"""Regression coverage for the companion's asynchronous ownership and outbound privacy boundaries."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from agent_core.config import Settings
from agent_core.contracts import document
from agent_core.engine import companion
from agent_core.engine.checkins import CheckinDesk
from agent_core.engine.companion import CompanionContext, CompanionDesk
from agent_core.engine.profile_scope import ProfileChanged
from agent_core.providers.scripted import ScriptedProvider
from agent_core.store.ids import new_ulid
from engine_harness import close, make_engine
from jsonschema import Draft202012Validator
from memory_harness import CAPTURE, PROFILE_B, bind, store
from test_m10a_profiles import student
from w8_companion_harness import calls, turn

NOTE = "Mixes up distance and displacement in speed questions"


@pytest.mark.parametrize("change", ["switch", "lock", "delete"])
def test_delayed_opener_cannot_write_or_return_after_profile_switch(
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    async def go() -> None:
        first, second = store(), store(PROFILE_B)
        current = {"learner": second.learner}
        schema = document("agents/companion-turn")
        desk = CompanionDesk(lambda: current["learner"], first.clock, Settings())

        def start() -> str:
            sid = new_ulid()
            current["learner"].conn.execute(
                "INSERT INTO sessions (session_id, mode, started_at) VALUES (?, 'study_companion', ?)",
                (sid, first.clock()),
            )
            return "ses_" + sid

        await desk.open(start, lambda _: True)
        before = second.conn.execute("SELECT opener_json FROM companion_episodes").fetchone()[0]
        current["learner"] = first.learner
        entered, release = asyncio.Event(), asyncio.Event()

        async def delayed(*_: Any) -> tuple[str, str]:
            entered.set()
            await release.wait()
            return "Private opener for the first learner", "model"

        monkeypatch.setattr(companion, "word_opener", delayed)
        desk.schema = lambda: ("companion", schema, Draft202012Validator(schema))
        task = asyncio.create_task(desk.open(start, lambda _: True))
        await asyncio.wait_for(entered.wait(), 3)
        current["learner"] = second.learner if change == "switch" else None
        if change == "delete":
            first.conn.close()
        release.set()
        outcome = (await asyncio.gather(task, return_exceptions=True))[0]
        assert second.conn.execute("SELECT opener_json FROM companion_episodes").fetchone()[0] == before
        assert isinstance(outcome, LookupError), "the old request must not return either learner's data"

    asyncio.run(go())


@pytest.mark.parametrize("with_note", [False, True])
def test_actual_cloud_turn_uses_only_the_cloud_profile(tmp_path: Path, with_note: bool) -> None:
    async def go() -> None:
        held = store()
        held.conn.execute("UPDATE profile SET reading_level = 'support', support_level = 'extra'")
        if with_note:
            held.note(NOTE, new_ulid())
        cloud = ScriptedProvider({"companion": [turn("What would you like to practise?")]}, kind="cloud")
        engine, local = await make_engine(tmp_path, {}, cloud=cloud, worker=False, stage="S2")
        try:
            local.installed_models = []
            engine.deps.router.cloud_on = lambda _: True
            bind(engine, held)
            engine.companion = CompanionContext(CompanionDesk(lambda: held.learner, held.clock, engine.deps.settings))
            await engine.companion_turn("Where should I start today?")
            sent = [r for r in cloud.requests if r.get("_role") == "companion"]
            assert len(sent) == 1, "exercise the real cloud request, not a canned response after prepare fails"
            wire = json.dumps(sent[0]["messages"])
            assert "reading level support" not in wire and "support extra" not in wire
            assert NOTE not in wire
            assert "O level" in wire and "physics" in wire
        finally:
            await close(engine)

    asyncio.run(go())


def test_consent_is_rechecked_between_cloud_tool_rounds(tmp_path: Path) -> None:
    async def go() -> None:
        held = store()
        held.note(NOTE, new_ulid())
        consent = {"on": True}

        def withdraw(_: Any) -> dict[str, Any]:
            consent["on"] = False
            return calls(("memory_recall", {"query_id": "recent_notes", "refs": []}))

        cloud = ScriptedProvider({"companion": [withdraw, turn("What shall we work on?")]}, kind="cloud")
        engine, local = await make_engine(tmp_path, {}, cloud=cloud, worker=False, stage="S2")
        try:
            local.installed_models = []
            engine.deps.router.cloud_on = lambda _: True
            bind(engine, held)
            engine.memory.memory_online = lambda: consent["on"]
            engine.companion = CompanionContext(CompanionDesk(lambda: held.learner, held.clock, engine.deps.settings))
            await engine.companion_turn("What did I struggle with?")
            sent = [r for r in cloud.requests if r.get("_role") == "companion"]
            assert len(sent) == 1  # derived context cannot be sent again after its permission is withdrawn
            assert NOTE in json.dumps(sent[0]["messages"])
        finally:
            await close(engine)

    asyncio.run(go())


@pytest.mark.parametrize("withdraw", ["memory", "materials", "profile"])
def test_cloud_retry_rechecks_permissions_at_dispatch(tmp_path: Path, withdraw: str) -> None:
    async def go() -> None:
        held, other = store(), store(PROFILE_B)
        held.note(NOTE, new_ulid())
        current = {"learner": held.learner}
        consent = {"memory": True, "materials": True}

        def revoke(_: Any) -> dict[str, Any]:
            if withdraw == "profile":
                current["learner"] = other.learner
            else:
                consent[withdraw] = False
            return {"error": {"status": 429}}

        cloud = ScriptedProvider({"companion": [revoke, turn("This retry must never leave.")]}, kind="cloud")
        engine, local = await make_engine(tmp_path, {}, cloud=cloud, worker=False, stage="S2")
        try:
            local.installed_models = []
            engine.deps.router.cloud_on = lambda _: True
            bind(engine, held)
            engine.memory.memory_online = lambda: consent["memory"]
            engine.companion = CompanionContext(
                CompanionDesk(lambda: current["learner"], held.clock, engine.deps.settings),
                share_materials=lambda: consent["materials"],
            )
            if withdraw == "profile":
                with pytest.raises(ProfileChanged):
                    await engine.companion_turn("What did I struggle with?")
            else:
                await engine.companion_turn("What did I struggle with?")
            assert len([r for r in cloud.requests if r.get("_role") == "companion"]) == 1
        finally:
            await close(engine)

    asyncio.run(go())


@pytest.mark.parametrize("retain_connection", [False, True])
def test_delayed_checkin_cannot_write_to_a_stale_profile(retain_connection: bool) -> None:
    async def go() -> None:
        first, second = store(day="2026-10-15"), store(PROFILE_B, day="2026-10-15")
        current = {"learner": first.learner}
        entered, release = asyncio.Event(), asyncio.Event()

        class Delayed:
            async def complete(self, *_: Any, **__: Any) -> Any:
                entered.set()
                await release.wait()
                return SimpleNamespace(
                    schema_valid=True,
                    structured={
                        "found": True,
                        "kind": "event_checkin",
                        "subject": "physics",
                        "due_day": "2026-10-17",
                        "text": "How did the mock paper go?",
                        "confidence": 0.9,
                    },
                )

        desk = CheckinDesk(
            lambda: current["learner"],
            first.clock,
            Settings(),
            capture=lambda: CAPTURE,
            schema=lambda: document("agents/commitment"),
        )
        task = asyncio.create_task(desk.extract(Delayed(), "mock paper on Saturday", "ses_x", local_only=True))
        await asyncio.wait_for(entered.wait(), 3)
        if retain_connection:
            desk.cancel_all()  # direct extraction can outlive cancellation of the scheduled task set
        else:
            current["learner"] = second.learner
        release.set()
        assert await task is None
        assert first.conn.execute("SELECT count(*) FROM commitments").fetchone()[0] == 0
        assert second.conn.execute("SELECT count(*) FROM commitments").fetchone()[0] == 0

    asyncio.run(go())


def test_compaction_cannot_retry_after_profile_switch(tmp_path: Path) -> None:
    async def go() -> None:
        first, second = store(), store(PROFILE_B)
        current = {"learner": first.learner}
        engine, _ = await make_engine(tmp_path, {}, worker=False, stage="S2")
        try:
            context = CompanionContext(CompanionDesk(lambda: current["learner"], first.clock, engine.deps.settings))
            engine.companion = context
            engine.state.transcript = [
                {"role": "user", "content": "A long discussion. " * 2000, "kind": "companion"} for _ in range(20)
            ]
            attempts: list[str] = []

            async def summarise(dialogue: str) -> str:
                attempts.append(dialogue)
                current["learner"] = second.learner
                return "We agreed to do 987654321 exercises."  # would normally cause the compactor's repair call

            engine.auxiliary.summariser = lambda **_: summarise
            with pytest.raises(ProfileChanged):
                await companion._history(engine, context)
            assert len(attempts) == 1
        finally:
            await close(engine)

    asyncio.run(go())


def test_cloud_fallback_cannot_replay_local_tool_results(tmp_path: Path) -> None:
    async def go() -> None:
        held = store()
        held.note(NOTE, new_ulid())
        cloud = ScriptedProvider({"companion": [turn("Let's practise together.")]}, kind="cloud")
        engine, local = await make_engine(
            tmp_path,
            {
                "companion": [
                    calls(("memory_recall", {"query_id": "preferences", "refs": []})),
                    {"error": {"status": 404}},
                ]
            },
            cloud=cloud,
            worker=False,
            stage="S2",
        )
        try:
            bind(engine, held)
            engine.companion = CompanionContext(CompanionDesk(lambda: held.learner, held.clock, engine.deps.settings))
            engine.deps.router.cloud_on = lambda _: False
            original = engine.deps.router.complete

            async def complete(*args: Any, **kwargs: Any) -> Any:
                result = await original(*args, **kwargs)
                if args[0] == "companion":
                    # The first successful local tool round is followed by loss of the local model.
                    local.installed_models = []
                    engine.deps.router.cloud_on = lambda _: True
                return result

            engine.deps.router.complete = complete
            await engine.companion_turn("Which explanations help me?")
            assert any(r.get("_role") == "companion" for r in local.requests)
            assert not [r for r in cloud.requests if r.get("_role") == "companion"], (
                "a local model's unscreened tool arguments and results must not silently migrate to cloud"
            )
        finally:
            await close(engine)

    asyncio.run(go())


def test_cloud_history_omits_local_and_revoked_memory_derived_replies(tmp_path: Path) -> None:
    async def go() -> None:
        held = store()
        cloud = ScriptedProvider({"companion": [turn("What would you like to practise?")]}, kind="cloud")
        engine, local = await make_engine(tmp_path, {}, cloud=cloud, worker=False, stage="S2")
        try:
            local.installed_models = []
            engine.deps.router.cloud_on = lambda _: True
            bind(engine, held)
            engine.companion = CompanionContext(CompanionDesk(lambda: held.learner, held.clock, engine.deps.settings))
            engine.state.transcript.extend(
                [
                    {
                        "role": "assistant",
                        "kind": "companion",
                        "content": "LOCAL_PRIVATE_SENTINEL",
                        "companion_egress": {"local_only": True},
                    },
                    {
                        "role": "assistant",
                        "kind": "companion",
                        "content": "REVOKED_NOTE_SENTINEL",
                        "companion_egress": {"memory": True},
                    },
                    {"role": "assistant", "kind": "companion", "content": "OLDER_UNKNOWN_SENTINEL"},
                    {
                        "role": "assistant",
                        "kind": "companion",
                        "content": "PUBLIC_CONTINUITY_SENTINEL",
                        "companion_egress": {},
                    },
                ]
            )
            await engine.companion_turn("Where should I start today?")
            sent = [r for r in cloud.requests if r.get("_role") == "companion"]
            assert len(sent) == 1
            wire = json.dumps(sent[0]["messages"])
            assert "PUBLIC_CONTINUITY_SENTINEL" in wire
            for marker in ("LOCAL_PRIVATE_SENTINEL", "REVOKED_NOTE_SENTINEL", "OLDER_UNKNOWN_SENTINEL"):
                assert marker not in wire
        finally:
            await close(engine)

    asyncio.run(go())


def test_queued_open_keeps_the_profile_that_requested_it() -> None:
    async def go() -> None:
        first, second = store(), store(PROFILE_B)
        current = {"learner": first.learner}
        desk = CompanionDesk(lambda: current["learner"], first.clock, Settings())
        started: list[str] = []
        await desk._lock.acquire()
        task = asyncio.create_task(desk.open(lambda: started.append("unexpected") or "ses_x", lambda _: True))
        await asyncio.sleep(0)  # let open capture its scope and wait on the desk lock
        current["learner"] = second.learner
        desk._lock.release()
        with pytest.raises(ProfileChanged):
            await task
        assert started == []
        assert second.conn.execute("SELECT count(*) FROM companion_summary").fetchone()[0] == 0

    asyncio.run(go())


def test_invalidation_rejects_a_retained_learner_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    async def go() -> None:
        held = store()
        desk = CompanionDesk(lambda: held.learner, held.clock, Settings())
        opened = await desk.open(lambda: "ses_" + held.session(new_ulid()), lambda _: True)
        episode = desk.episode(opened["opener"]["opener_id"])
        before = held.conn.execute("SELECT opener_json FROM companion_episodes").fetchone()[0]
        episode.opener = {}  # force fresh wording, as a changed fact would

        async def invalidate(*_: Any) -> tuple[str, str]:
            desk.invalidate(held.profile)  # a close/reopen can retain this same learner while work drains
            return "Stale reply", "model"

        monkeypatch.setattr(companion, "word_opener", invalidate)
        desk.schema = lambda: ("companion", {}, Draft202012Validator({}))
        with pytest.raises(ProfileChanged):
            await desk.opener(episode, held.clock())
        assert held.conn.execute("SELECT opener_json FROM companion_episodes").fetchone()[0] == before

    asyncio.run(go())


@pytest.mark.parametrize("during", ["guard", "reply"])
def test_turn_drops_results_when_its_profile_changes(tmp_path: Path, during: str) -> None:
    async def go() -> None:
        first, second = store(), store(PROFILE_B)
        current = {"learner": first.learner}

        def switch(_: Any) -> dict[str, Any]:
            current["learner"] = second.learner
            return turn("Private reply for the first learner")

        engine, _ = await make_engine(tmp_path, {"companion": [switch]}, worker=False, stage="S2")
        try:
            bind(engine, first)
            engine.companion = CompanionContext(
                CompanionDesk(lambda: current["learner"], first.clock, engine.deps.settings)
            )
            if during == "guard":

                async def guard(*_: Any, **__: Any) -> Any:
                    current["learner"] = second.learner
                    return None

                engine._guard_model = guard
            with pytest.raises(ProfileChanged):
                await engine.companion_turn("Where should I start today?")
            assert not [r for r in engine.state.transcript if r.get("kind") == "companion"]
            assert second.conn.execute("SELECT count(*) FROM companion_summary").fetchone()[0] == 0
        finally:
            await close(engine)

    asyncio.run(go())


def test_late_events_and_checkpoints_cannot_reach_switched_or_reopened_profiles(tmp_path: Path) -> None:
    from w8_companion_harness import stop_core, thread

    async def go() -> None:
        t = await thread(tmp_path, {"companion": [turn("What shall we practise?")]})
        try:
            opened = await t.open()
            await t.say(opened["session_id"], "Where should I start today?")
            core = t.r.core
            original = core.sessions[opened["session_id"]]
            alice = original.profile_id
            other = await t.api.add(student("Ben"))
            await t.api.unlock(other)
            observed: list[Any] = []
            core.records.on_event = lambda *args: observed.append(args)
            core.planner = lambda: SimpleNamespace(current=lambda: observed.append("READ_OTHER_PLAN") or {})
            with pytest.raises(ProfileChanged):
                await original.engine.deps.executor.host_executors["plan"]({}, SimpleNamespace())
            # These callbacks can arrive even after the old session's stream has closed.
            part = original.engine.events.start_part("text")
            original.engine.events.text(part, "PRIVATE_LATE_CALLBACK")
            original.engine.events.end_part(part)
            assert observed == []
            assert original.session_id not in core.store.load_all()

            await t.api.unlock(alice)
            assert core.sessions[original.session_id] is not original
            original.engine_state.transcript.append({"role": "assistant", "content": "STALE_CHECKPOINT"})
            core.persist(original)
            assert "STALE_CHECKPOINT" not in json.dumps(core.store.load_all())
        finally:
            await stop_core(t.r)

    asyncio.run(go())


def test_cloud_current_session_recall_cannot_bypass_history_provenance() -> None:
    from agent_core.engine.memory_session import MemoryAccess, SessionMemory
    from agent_core.engine.memory_tools import MemoryTools
    from agent_core.tools.spec import InvalidArguments

    held = store()
    sid = held.session("A" * 26)
    held.conn.execute(
        "INSERT INTO turns(turn_id,session_id,idx,speaker,status,student_text,started_at)"
        " VALUES ('private',?,0,'student','complete','PRIVATE_LOCAL_ONLY',?)",
        (sid, held.clock.now),
    )
    memory = SessionMemory(MemoryAccess(held.profile, held.source), Settings(), "ses_" + sid)
    tools = MemoryTools(memory, Settings(), lambda: True)
    context = SimpleNamespace(session=SimpleNamespace(role="companion", session_id="ses_" + sid))
    with pytest.raises(InvalidArguments):
        asyncio.run(tools.search({"scope": "current", "pattern": "PRIVATE_LOCAL_ONLY"}, context))


@pytest.mark.parametrize("local_available", [False, True])
def test_companion_compaction_cannot_send_private_history_to_cloud(tmp_path: Path, local_available: bool) -> None:
    from engine_harness import reply

    async def go() -> None:
        held = store()
        cloud = ScriptedProvider(
            {
                "compaction": [reply(json.dumps({"agreements": "Return to the example."}))],
                "companion": [turn("What would you like to continue?")],
            },
            kind="cloud",
        )
        engine, local = await make_engine(
            tmp_path,
            {"compaction": [reply(json.dumps({"agreements": "Return to the example."}))]},
            cloud=cloud,
            worker=False,
            stage="S2",
        )
        try:
            if not local_available:
                local.installed_models = []
            engine.deps.router.cloud_on = lambda _: True
            bind(engine, held)
            engine.companion = CompanionContext(CompanionDesk(lambda: held.learner, held.clock, engine.deps.settings))
            # A retained legacy checkpoint can exceed today's bounded history window.
            engine.state.transcript = [
                {
                    "role": "user",
                    "content": "PRIVATE_SUMMARY_SENTINEL " + "discussion " * 200,
                    "kind": "companion",
                    "companion_egress": {"local_only": True},
                }
                for _ in range(20)
            ]
            await engine.companion_turn("Continue our conversation.")
            assert engine.compactor.history, "exercise actual compaction"
            assert "PRIVATE_SUMMARY_SENTINEL" not in json.dumps(cloud.requests)
            assert not [r for r in cloud.requests if r.get("_role") == "compaction"]
            if local_available:
                assert [r for r in local.requests if r.get("_role") == "compaction"]
                assert engine.compactor.history[-1].sections["Agreements"].endswith("Return to the example.")
        finally:
            await close(engine)

    asyncio.run(go())
