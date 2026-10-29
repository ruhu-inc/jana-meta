"""The personal learning agent's routes (SPEC §19, W8).

- `GET /v1/companion/opener` (phase 1): the Last time card on Home and in Study: facts by code from the open
  profile's learner database, worded by the engine's templates, no model call (§19.5.2).
- `POST /v1/companion` (phase 2): today's episode of the thread, opened or resumed (`CompanionOpened`); the opener is
  in this reply only, never on the stream. Turns go through `POST /v1/sessions/{session_id}/turns`.
- `GET /v1/companion/summary` (phase 2): the thread's rolling summary, folded by code (§19.5.3).
- Check-ins (phase 3, §19.3.4, §19.5.5): `GET /v1/checkins/due` (at most one, chosen in one transaction),
  `POST /v1/checkins/{commitment_id}/dismiss`, and `POST /v1/checkins/{commitment_id}/open` (the thread's episode,
  opened with the check-in's question; its first accepted turn answers it)."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, Response

from agent_core.api.core import CURRENT_PROFILE, CoreService, require
from agent_core.api.errors import ApiError
from agent_core.api.profiles import Mutating
from agent_core.engine.companion_opener import OpenerDesk


def add_routes(app: FastAPI, core: CoreService, mutating: Mutating) -> None:
    @app.get("/v1/companion/opener")
    async def opener() -> Any:
        if core.directory is not None and core.directory.exists() and CURRENT_PROFILE.get() != core.records_profile:
            raise ApiError("not_found", "this profile is not open")
        records = core.records
        if records is None or records.learner is None or core.records_profile is None:
            raise ApiError("not_found", "the card needs an open learner database")
        return OpenerDesk(records.learner, core.settings, core.clock_ms).opener()

    def opened() -> None:
        if core.directory is not None and core.directory.exists() and CURRENT_PROFILE.get() != core.records_profile:
            raise ApiError("not_found", "this profile is not open")
        if core.tutor_unavailable is not None and core.tutor_unavailable():
            raise ApiError("model_unavailable", "the tutor cannot run on this computer offline")

    @app.post("/v1/companion")
    async def open_thread(request: Request) -> Response:
        async def run(body: Any) -> tuple[int, Any]:
            opened()
            require("CompanionOpen", body or {})
            try:
                reply = await core.open_companion()
            except LookupError:
                raise ApiError("not_found", "the companion needs an open learner database") from None
            return 200, require("CompanionOpened", reply)

        return await mutating(request, run)

    @app.get("/v1/companion/summary")
    async def summary() -> Any:
        if core.directory is not None and core.directory.exists() and CURRENT_PROFILE.get() != core.records_profile:
            raise ApiError("not_found", "this profile is not open")
        try:
            return require("CompanionSummary", core.companion.fold())
        except LookupError:
            raise ApiError("not_found", "the summary needs an open learner database") from None

    def profile_open() -> None:
        if core.directory is not None and core.directory.exists() and CURRENT_PROFILE.get() != core.records_profile:
            raise ApiError("not_found", "this profile is not open")
        if core.records is None or core.records.learner is None or core.records_profile is None:
            raise ApiError("not_found", "check-ins need an open learner database")

    @app.get("/v1/checkins/due")
    async def checkins_due() -> Any:
        profile_open()
        return require("CheckinsDue", {"items": core.checkins.due()})

    @app.post("/v1/checkins/{commitment_id}/dismiss")
    async def checkin_dismiss(commitment_id: str, request: Request) -> Response:
        async def run(body: Any) -> tuple[int, Any]:
            profile_open()
            try:
                return 200, require("Commitment", core.checkins.dismiss(commitment_id))
            except LookupError:
                raise ApiError("not_found", "no such check-in") from None

        return await mutating(request, run)

    @app.post("/v1/checkins/{commitment_id}/open")
    async def checkin_open(commitment_id: str, request: Request) -> Response:
        async def run(body: Any) -> tuple[int, Any]:
            opened()
            profile_open()
            try:
                checkin = core.checkins.opening(commitment_id)
            except LookupError:
                raise ApiError("not_found", "no such check-in") from None
            return 200, require("CompanionOpened", await core.open_companion(checkin=checkin))

        return await mutating(request, run)
