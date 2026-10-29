"""Shared fixtures for the W8 phase 2 tests: an API core at stage S2 with a scripted local model and a profile, the
companion's open and turns through the real routes, and the scripted model's companion replies. Synthetic data."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from agent_core.config import Settings
from api_harness import Running, ask, stop_core
from engine_harness import reply
from journey_harness import restart, scripted, start
from test_m10a_profiles import Api, student


def turn(text: str, action: dict[str, Any] | None = None) -> dict[str, Any]:
    """A scripted companion reply (the companion-turn contract)."""
    return reply(json.dumps({"text": text, "action": action}))


def calls(*items: tuple[str, dict[str, Any]]) -> dict[str, Any]:
    """A scripted companion reply that calls tools."""
    return reply("", [(f"c{i}", name, args) for i, (name, args) in enumerate(items)])


class Thread:
    """One profile's API core with the companion's routes."""

    def __init__(self, r: Running, api: Api, token: str) -> None:
        self.r, self.api, self.token = r, api, token

    async def open(self) -> dict[str, Any]:
        reply_ = await self.api.call("POST", "/v1/companion", {}, profile=self.token)
        assert reply_.status_code == 200, reply_.text
        return dict(reply_.json())

    async def say(self, session_id: str, text: str) -> dict[str, Any]:
        sent = await self.api.call("POST", f"/v1/sessions/{session_id}/turns", ask(text), profile=self.token)
        assert sent.status_code == 202, sent.text
        await self.r.wait_idle(session_id)
        return dict(sent.json())

    async def snapshot(self, session_id: str) -> dict[str, Any]:
        got = await self.api.call("GET", f"/v1/sessions/{session_id}/snapshot", profile=self.token)
        assert got.status_code == 200, got.text
        return dict(got.json())

    def companion_requests(self) -> list[dict[str, Any]]:
        return [q for q in self.r.runtime.providers["local"].requests if q.get("_role") == "companion"]


def settings(**extra: Any) -> Settings:
    return Settings(worker_pool_size=1, worker_respawn_backoff_s=(0.0,), study_workspace_enabled=True,
                    study_offline_enabled=True, **extra)  # fmt: skip


async def thread(tmp_path: Path, script: dict[str, list[Any]], **extra: Any) -> Thread:
    """The app's core at stage S2 over a data folder with the physics pack installed, and one adult profile open."""
    r = await start(tmp_path, provider=scripted(script), settings=settings(**extra), worker=False)
    r.core.research_router = None  # the opener's wording takes its template here (tested on its own in test_w8_opener)
    api = Api(r)
    profile = await api.add(student("Ada"))
    token = (await api.unlock(profile)).json()["profile_token"]
    return Thread(r, api, token)


async def reopen(t: Thread, script: dict[str, list[Any]], **extra: Any) -> Thread:
    """The app closed and started again on the same data folder, the same profile opened."""
    r = await restart(t.r, provider=scripted(script), settings=settings(**extra), worker=False)
    r.core.research_router = None
    api = Api(r)
    profiles = (await api.call("GET", "/v1/profiles")).json()["profiles"]
    token = (await api.unlock(profiles[0]["profile_id"])).json()["profile_token"]
    return Thread(r, api, token)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


__all__ = ["Thread", "calls", "reopen", "run", "stop_core", "thread", "turn"]
