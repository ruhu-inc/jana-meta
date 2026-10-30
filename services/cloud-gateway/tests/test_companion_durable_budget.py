"""Daily admission survives session rotation and never trusts a tool message as proof of a counted turn."""

from pathlib import Path

from cloud_gateway.companion import CompanionLedger
from cloud_gateway.errors import DeviceError
from gateway_stubs import gateway_config, harness
from test_w8_companion_limits import TOOL_ROUND, TURN


def test_new_session_and_recreated_ledger_do_not_reset_the_daily_budget(tmp_path: Path) -> None:
    h = harness(gateway_config(tmp_path, slots={"primary": "meta"}))
    gw = h.client._transport.app.state.gateway
    model = gw.providers.resolve("primary/fast-model")[2]
    for i in range(60):
        ledger = CompanionLedger(h.config, gw.store, h.clock)
        result = ledger.admit("authenticated-account", f"session-{i}", "companion", model, TURN, h.clock())
        assert isinstance(result, tuple)
        ledger.settle(result[0], 0)
    result = ledger.admit("authenticated-account", "restored-profile-session", "companion", model, TURN, h.clock())
    assert isinstance(result, DeviceError) and result.code == "plan_limit"


def test_tool_result_cannot_bypass_admission(tmp_path: Path) -> None:
    h = harness(gateway_config(tmp_path, slots={"primary": "meta"}))
    gw = h.client._transport.app.state.gateway
    model = gw.providers.resolve("primary/fast-model")[2]
    for _ in range(60):
        result = gw.companion.admit("account", "session", "companion", model, TOOL_ROUND, h.clock())
        assert isinstance(result, tuple)
        gw.companion.settle(result[0], 0)
    result = gw.companion.admit("account", "session", "companion", model, TOOL_ROUND, h.clock())
    assert isinstance(result, DeviceError) and result.code == "plan_limit"


def test_logical_operation_counts_once_but_every_attempt_reserves_spend(tmp_path: Path) -> None:
    h = harness(gateway_config(tmp_path, slots={"primary": "meta"}))
    gw = h.client._transport.app.state.gateway
    model = gw.providers.resolve("primary/fast-model")[2]
    operation = "synthetic-operation-0001"
    for i in range(12):
        result = gw.companion.admit(
            "account",
            f"session-{i}",
            "companion",
            model,
            TURN if i == 0 else TOOL_ROUND,
            h.clock(),
            operation_id=operation,
        )
        assert isinstance(result, tuple)
    assert gw.store._db.execute("SELECT counted FROM companion_days").fetchone()[0] == 1
    assert gw.store._db.execute("SELECT count(*) FROM companion_holds").fetchone()[0] == 12
    refused = gw.companion.admit("account", "new-session", "companion", model, TURN, h.clock(), operation_id=operation)
    assert isinstance(refused, DeviceError)
    # Abandoned calls keep their holds across ledger reconstruction: a crash cannot forgive uncertain spend.
    ledger = CompanionLedger(h.config, gw.store, h.clock)
    ledger.per_day_micros = 1
    assert isinstance(ledger.admit("account", "new", "companion", model, TURN, h.clock()), DeviceError)
