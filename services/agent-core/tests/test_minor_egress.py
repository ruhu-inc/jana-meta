"""PRD-21 under the explicit D86/D87 scope rules. Learners, DPIA and entitlement keys are synthetic."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from api_harness import start_core, stop_core
from net_harness import FakeServices, layer
from signing_service.hierarchy import dev_trust
from test_m10a_profiles import Api, code, student
from test_m10e_consent import _settings


@pytest.mark.parametrize("band", ["under_13", "13_15", "16_17"])
def prd21_minor_needs_guardian_consent(tmp_path: Path, band: str) -> None:
    """No learner under 18 is served (W5): the profile is never made, so no feature can send anything for one, and
    nothing leaves the device while the request is refused."""

    async def scenario() -> None:
        r = await start_core(tmp_path, settings=_settings(), worker=False, stage="S2")
        r.core.entitlement_trust = dev_trust()
        try:
            async with FakeServices(tmp_path) as fake:
                online = layer(tmp_path, fake, device=r.runtime.stores.device)
                r.core.online = r.runtime.online = online
                try:
                    api = Api(r)
                    before = len(fake.requests)
                    refused = await api.call("POST", "/v1/profiles", student("Synthetic learner", age_band=band))
                    assert code(refused) == "validation_failed"
                    assert (await api.call("GET", "/v1/profiles")).json()["profiles"] == []
                    assert len(fake.requests) == before, "a refused profile sends nothing"
                finally:
                    await online.stop()
        finally:
            await stop_core(r)

    asyncio.run(scenario())
