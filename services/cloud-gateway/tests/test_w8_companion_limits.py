"""W8 phase 3 (SPEC §19.4, §19.7, §19.8): the gateway admits the personal learning agent's calls on the chat route by
the role the device names. A Study companion turn or a Reflector job holds its upper bound in the ledger under its own
feature (`companion`, `reflector`), counts against the plan's `companion_turns_per_day` (60) or
`tutor_memory_jobs_per_day` (20) per session pseudonym per day, and is refused with `plan_limit` at the cap; the
shipped configuration types the new keys and still refuses unknown ones. Provider replies are scripted and every
learner value is synthetic."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from cloud_gateway import companion, minimise, plans
from cloud_gateway.config import load_config
from cloud_gateway.inference_budget import micros
from gateway_stubs import Device, gateway_config, harness
from pydantic import ValidationError

TURN = {"model": "primary/fast-model", "max_tokens": 256,
        "messages": [{"role": "system", "content": "You are the synthetic Study companion."},
                     {"role": "user", "content": "Quiz me on uniform acceleration."}]}  # fmt: skip
TOOL_ROUND = {**TURN, "messages": [
    *TURN["messages"],
    {"role": "assistant", "content": None, "tool_calls": [
        {"id": "call_1", "type": "function", "function": {"name": "search_sources", "arguments": "{}"}}]},
    {"role": "tool", "tool_call_id": "call_1", "content": "{\"hits\": []}"},
]}  # fmt: skip


async def ask(h: Any, device: Device, role: str, body: dict[str, Any] = TURN) -> Any:
    return await h.client.post("/v1/chat/completions", json=body, headers={**device.headers(), "X-Jana-Role": role})


def rows(gw: Any, sql: str) -> list[tuple[Any, ...]]:
    with gw.store._lock:
        return list(gw.store._db.execute(sql).fetchall())


def test_the_61st_turn_is_refused_with_plan_limit(tmp_path: Path) -> None:
    async def run() -> None:
        h = harness(gateway_config(tmp_path, slots={"primary": "meta"}))
        device = Device()
        await device.login(h.client)
        for _ in range(60):
            assert (await ask(h, device, "companion")).status_code == 200
        refused = await ask(h, device, "companion")
        assert refused.status_code == 429 and refused.json()["error"]["code"] == "plan_limit"
        assert "quota" not in refused.text.lower()  # only the companion stops: the device keeps the cloud tier
        assert 0 < int(refused.headers["retry-after"]) <= 86400
        assert len(h.stubs["meta"].seen) == 60  # the 61st never reached the provider
        # The tool round of a turn already counted continues it; another role is not counted at all.
        assert (await ask(h, device, "companion", TOOL_ROUND)).status_code == 200
        assert (await ask(h, device, "coach")).status_code == 200
        # The count is per session pseudonym: the next session of the day starts its own.
        other = Device(key=device.key, credential_id=device.credential_id, token=device.token)
        assert (await ask(h, other, "companion")).status_code == 200
        assert (await ask(h, device, "companion")).status_code == 429
        # Nothing stored names the pseudonym; the rows are keyed by the day's hash.
        assert device.pseudonym not in repr(rows(h.client._transport.app.state.gateway, "SELECT * FROM companion_days"))
        # At midnight UTC the day rolls over and the same session is admitted again.
        h.clock.now += 86400
        await device.login(h.client)
        assert (await ask(h, device, "companion")).status_code == 200
        await h.client.aclose()

    asyncio.run(run())


def test_a_reflector_job_reserves_its_bound_under_its_feature(tmp_path: Path) -> None:
    async def run() -> None:
        quotas = {"device_burst": 1000, "licence_burst": 10000, "deployment_total_spend_usd": 5.0}
        h = harness(gateway_config(tmp_path, slots={"primary": "meta"}, quotas=quotas))
        gw = h.client._transport.app.state.gateway
        model = gw.providers.resolve("primary/fast-model")[2]
        sent = companion.bounded(h.config, minimise.forwarded(TURN))
        bound = micros(companion.bound_usd(h.config, model, sent))
        assert sent["max_completion_tokens"] == 256 and "max_tokens" not in sent and bound > 0

        # The ledger holds the job's upper bound under `reflector` while it runs, then its cost instead.
        admitted = gw.companion.admit("sub_synthetic", "synthetic-pseudonym", "reflector", model,
                                      minimise.forwarded(TURN), h.clock())  # fmt: skip
        assert isinstance(admitted, tuple)
        key = admitted[0]
        assert rows(gw, "SELECT feature, counted, held_micros, spent_micros FROM companion_days") == [
            ("reflector", 1, bound, 0)
        ]
        gw.companion.settle(key, 0.000125)
        assert rows(gw, "SELECT feature, counted, held_micros, spent_micros FROM companion_days") == [
            ("reflector", 1, 0, micros(0.000125))
        ]

        # Through the chat route: the deployment's ledger holds the same bound under the feature, and the request row
        # is recorded under it.
        device = Device()
        await device.login(h.client)
        assert (await ask(h, device, "reflector")).status_code == 200
        assert h.stubs["meta"].seen[-1].body["max_completion_tokens"] == 256
        assert rows(gw, "SELECT role, reserved_micros, outcome FROM inference_budget_holds") == [
            ("reflector", bound, "settled")
        ]
        assert rows(gw, "SELECT feature FROM requests") == [("reflector",)]
        # Twenty jobs a day (one counted above); the 21st is refused before any provider sees it.
        for _ in range(19):
            assert (await ask(h, device, "reflector")).status_code == 200
        refused = await ask(h, device, "reflector")
        assert refused.status_code == 429 and refused.json()["error"]["code"] == "plan_limit"
        assert len(h.stubs["meta"].seen) == 20
        # Companion turns are counted apart, under their own feature, in the same session.
        assert (await ask(h, device, "companion")).status_code == 200
        assert rows(gw, "SELECT role FROM inference_budget_holds ORDER BY created_at, rowid")[-1] == ("companion",)
        assert rows(gw, "SELECT feature, count(*) FROM requests GROUP BY feature ORDER BY feature") == [
            ("companion", 1), ("reflector", 20)
        ]  # fmt: skip
        assert gw.inference_budget.snapshot()["held_usd"] == 0
        # The day's spend cap is held against the bound: a call whose bound would pass it is refused too.
        gw.companion.per_day_micros = bound
        assert (await ask(h, device, "companion")).json()["error"]["code"] == "plan_limit"
        await h.client.aclose()

    asyncio.run(run())


def test_unknown_toml_keys_still_fail_and_the_typed_ones_load(tmp_path: Path) -> None:
    shipped = load_config()
    assert shipped.companion.per_day_usd == 0.50
    for plan in shipped.plans.paid.values():
        assert (plan.limits.companion_turns_per_day, plan.limits.tutor_memory_jobs_per_day) == (60, 20)
    assert (companion.daily_cap(shipped, "companion"), companion.daily_cap(shipped, "reflector")) == (60, 20)
    # The entitlement signs only what its contract's `PlanLimits` names: the gateway holds the agent's caps itself.
    schema = json.loads((Path(plans.__file__).parent / "contracts" / "schemas" / "ops" / "licence.schema.json")
                        .read_text())["$defs"]["PlanLimits"]["properties"]  # fmt: skip
    for plan in shipped.plans.paid.values():
        assert set(plan.limits.granted()) <= set(schema)
        assert not {"companion_turns_per_day", "tutor_memory_jobs_per_day"} & set(plan.limits.granted())

    # A deployment file sets the typed keys; the rest keep the shipped values.
    deployment = tmp_path / "gateway.toml"
    deployment.write_text("[companion]\nper_day_usd = 0.25\n\n[plans.paid.jana_online.limits]\n"
                          "companion_turns_per_day = 10\n")  # fmt: skip
    loaded = load_config(deployment)
    assert loaded.companion.per_day_usd == 0.25
    assert loaded.plans.paid["jana_online"].limits.companion_turns_per_day == 10
    assert loaded.plans.paid["jana_online"].limits.tutor_memory_jobs_per_day == 20
    assert companion.daily_cap(loaded, "companion") == 10  # the lowest a paid plan sets
    # Unset everywhere is no cap.
    unset = {"limits": {"companion_turns_per_day": None}}
    assert companion.daily_cap(load_config(plans={"paid": {"jana_online": unset, "jana_family": unset}}),
                               "companion") is None  # fmt: skip

    # `_Strict` still refuses a key it does not declare, at every level, and a negative cap.
    for text in ("[companion]\nper_day_usd = 0.5\nper_week_usd = 2.0\n",
                 "[companion_limits]\nturns = 60\n",
                 "[plans.paid.jana_online.limits]\ncompanion_turns_per_week = 300\n",
                 "[plans.free.limits]\ntutor_memory_jobs_per_week = 5\n",
                 "[plans.paid.jana_family.limits]\ntutor_memory_jobs_per_day = -1\n",
                 "[companion]\nper_day_usd = -0.5\n"):  # fmt: skip
        deployment.write_text(text)
        with pytest.raises(ValidationError):
            load_config(deployment)
