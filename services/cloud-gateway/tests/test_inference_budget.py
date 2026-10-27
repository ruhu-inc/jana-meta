"""Real SQLite budget enforcement under concurrent sends, crashes, midnight and metadata purge. No paid calls."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from pathlib import Path

import httpx
import pytest
from cloud_gateway.config import load_config
from cloud_gateway.inference_budget import RELEASABLE, BudgetedAdapter, InferenceBudget
from cloud_gateway.providers.base import ProviderReply, ProviderRequest, StreamPart, UpstreamError, Usage
from cloud_gateway.store import GatewayStore
from gateway_stubs import Device, Output, gateway_config, harness

NOW = 1792716361.0  # 2026-10-23T00:46:01Z


# The ledger's arithmetic below is worked out at this price; the shipped price is checked in test_meta.py.
TEST_PRICE = {"input": 0.30, "cached_input": 0.06, "output": 0.90}


def config(**quotas):
    return load_config(quotas={"deployment_total_spend_usd": 1.0, **quotas}, prices={"muse-spark-1.3": TEST_PRICE})


def request(**body) -> ProviderRequest:
    model = load_config().providers["meta"].models["fast-model"]
    return ProviderRequest(
        model,
        {"messages": [{"role": "user", "content": "Help me with algebra."}], "max_tokens": 64, **body},
        "fake-session-pseudonym",
    )


@dataclass
class Adapter:
    usage: Usage = field(default_factory=lambda: Usage(100, 20))
    fail: bool = False
    sends: int = 0

    async def complete(self, request: ProviderRequest) -> ProviderReply:
        self.sends += 1
        if self.fail:
            raise UpstreamError("timeout")
        return ProviderReply({"choices": [{"message": {"content": "A hint."}}]}, self.usage)

    async def stream(self, request: ProviderRequest) -> AsyncGenerator[StreamPart]:
        self.sends += 1
        yield StreamPart({"choices": [{"delta": {"content": "A hint."}}]})
        if self.fail:
            raise UpstreamError("network_unavailable")
        yield StreamPart(None, self.usage)

    async def aclose(self) -> None:
        pass


@pytest.mark.parametrize("limit", ["deployment_daily_spend_usd", "deployment_total_spend_usd"])
def test_zero_cap_blocks_before_provider_send(tmp_path: Path, limit: str) -> None:
    store = GatewayStore(tmp_path)
    adapter = Adapter()
    bounded = BudgetedAdapter(adapter, InferenceBudget(config(**{limit: 0}), store, lambda: NOW))
    with pytest.raises(UpstreamError, match="budget exhausted"):
        asyncio.run(bounded.complete(request()))
    assert adapter.sends == 0
    store.close()


def test_parallel_connections_cannot_spend_the_same_headroom(tmp_path: Path) -> None:
    store = GatewayStore(tmp_path)
    limited = config(deployment_total_spend_usd=0.003, deployment_max_output_tokens=1024)
    InferenceBudget(limited, store, lambda: NOW)
    store.close()

    def reserve(_: int) -> bool:
        connection = GatewayStore(tmp_path)
        try:
            budget = InferenceBudget(limited, connection, lambda: NOW)
            budget.reserve(request(max_tokens=1024))
            return True
        except UpstreamError:
            return False
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(reserve, range(8))) == 1


def test_known_usage_settles_once_and_counters_survive_purge_restart_and_midnight(tmp_path: Path) -> None:
    store = GatewayStore(tmp_path)
    clock = [NOW]
    budget = InferenceBudget(config(), store, lambda: clock[0])
    key, bounded = budget.reserve(request())
    assert bounded.body["max_completion_tokens"] == 64 and "max_tokens" not in bounded.body
    held = budget.snapshot()["held_usd"]
    assert held > 0
    budget.settle(key, bounded, Usage(100, 20))
    budget.settle(key, bounded, Usage(100, 20))
    assert budget.snapshot() == {"spent_usd": 0.000048, "today_usd": 0.000048, "held_usd": 0}
    store.purge(NOW + 100 * 86400, 1)
    store.close()
    reopened = GatewayStore(tmp_path)
    clock[0] += 86400
    restricted = InferenceBudget(config(deployment_total_spend_usd=held + 0.000047), reopened, lambda: clock[0])
    assert restricted.snapshot() == {"spent_usd": 0.000048, "today_usd": 0, "held_usd": 0}
    with pytest.raises(UpstreamError, match="budget exhausted"):
        restricted.reserve(request())
    reopened.close()


def test_daily_spend_resets_but_unknown_reservations_do_not(tmp_path: Path) -> None:
    store = GatewayStore(tmp_path)
    clock = [NOW]
    budget = InferenceBudget(config(deployment_daily_spend_usd=0.002), store, lambda: clock[0])
    key, bounded = budget.reserve(request())
    budget.settle(key, bounded, Usage(100, 20))
    clock[0] += 86400
    budget.reserve(request())
    assert budget.snapshot()["today_usd"] == 0
    clock[0] += 86400
    with pytest.raises(UpstreamError, match="budget exhausted"):
        budget.reserve(request())
    store.close()


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("unknown", ["timeout", "missing_usage"])
def test_failures_and_missing_usage_keep_the_upper_bound(tmp_path: Path, stream: bool, unknown: str) -> None:
    store = GatewayStore(tmp_path)
    budget = InferenceBudget(config(), store, lambda: NOW)
    adapter = Adapter(usage=Usage() if unknown == "missing_usage" else Usage(100, 20), fail=unknown == "timeout")
    bounded = BudgetedAdapter(adapter, budget)

    async def run() -> None:
        if stream:
            _ = [part async for part in bounded.stream(request())]
        else:
            await bounded.complete(request())

    if unknown == "timeout":
        with pytest.raises(UpstreamError):
            asyncio.run(run())
    else:
        asyncio.run(run())
    assert adapter.sends == 1
    assert budget.snapshot()["held_usd"] > 0 and budget.snapshot()["spent_usd"] == 0
    store.close()


def test_cancelled_stream_retains_reservation(tmp_path: Path) -> None:
    store = GatewayStore(tmp_path)
    budget = InferenceBudget(config(), store, lambda: NOW)

    async def run() -> None:
        stream = BudgetedAdapter(Adapter(), budget).stream(request())
        await anext(stream)
        await stream.aclose()

    asyncio.run(run())
    assert budget.snapshot()["held_usd"] > 0
    store.close()


def test_completed_stream_releases_unused_reservation(tmp_path: Path) -> None:
    store = GatewayStore(tmp_path)
    budget = InferenceBudget(config(), store, lambda: NOW)

    async def run() -> None:
        return [part async for part in BudgetedAdapter(Adapter(), budget).stream(request())]

    asyncio.run(run())
    assert budget.snapshot()["spent_usd"] == 0.000048 and budget.snapshot()["held_usd"] == 0
    store.close()


def test_approval_expiry_and_output_bound_are_enforced(tmp_path: Path) -> None:
    store = GatewayStore(tmp_path)
    clock = [NOW]
    budget = InferenceBudget(
        config(deployment_budget_expires_at="2026-11-02T00:46:01Z", deployment_max_output_tokens=128),
        store,
        lambda: clock[0],
    )
    _, bounded = budget.reserve(request(max_tokens=64000, max_completion_tokens=8000))
    assert bounded.body["max_completion_tokens"] == 128
    clock[0] += 10 * 86400
    with pytest.raises(UpstreamError, match="period has ended"):
        budget.reserve(request())
    store.close()


def test_all_gateway_provider_paths_share_budget(tmp_path: Path) -> None:
    async def run() -> None:
        h = harness(gateway_config(tmp_path, slots={"primary": "meta"}, quotas={"deployment_total_spend_usd": 0}))
        device = Device()
        await device.login(h.client)
        response = await device.chat(
            h.client, {"model": "primary/fast-model", "messages": [{"role": "user", "content": "Help."}]}
        )
        assert response.status_code == 429
        assert h.stubs["meta"].seen == []
        gw = h.client._transport.app.state.gateway
        _, study_adapter, model = gw.providers.resolve(gw.config.study_model)
        with pytest.raises(UpstreamError, match="budget exhausted"):
            await study_adapter.complete(ProviderRequest(model, request().body, "fake-study-session"))
        assert h.stubs["meta"].seen == []
        await h.client.aclose()

    asyncio.run(run())


def test_gateway_counts_real_stream_usage_and_caps_output(tmp_path: Path) -> None:
    async def run() -> None:
        h = harness(
            gateway_config(
                tmp_path,
                slots={"primary": "meta"},
                quotas={"deployment_total_spend_usd": 1, "deployment_max_output_tokens": 128},
            )
        )
        device = Device()
        await device.login(h.client)
        h.stubs["meta"].say(Output(text="A hint."))
        response = await device.chat(
            h.client,
            {"model": "primary/fast-model", "stream": True, "messages": [{"role": "user", "content": "Help."}]},
        )
        assert response.status_code == 200
        assert h.stubs["meta"].seen[-1].body["max_completion_tokens"] == 128
        gw = h.client._transport.app.state.gateway
        assert gw.inference_budget.snapshot()["held_usd"] == 0
        assert gw.inference_budget.snapshot()["spent_usd"] > 0
        await h.client.aclose()

    asyncio.run(run())


def test_unbudgeted_paid_services_cannot_be_enabled() -> None:
    with pytest.raises(ValueError, match="does not cover search"):
        load_config(quotas={"deployment_total_spend_usd": 1},
                    ask_search={"url": "https://search.example.invalid", "secret": "fake-search-key"})  # fmt: skip


def test_voice_is_enabled_under_the_budget() -> None:
    """Cloud voice reserves its speech charges against the budget (SPEC §6.1), so the dev config can switch it on."""
    assert load_config(quotas={"deployment_total_spend_usd": 1}, voice_enabled=True).voice_enabled


@pytest.mark.parametrize("amount", [float("inf"), float("nan"), -1])
def test_invalid_budget_limits_are_refused(amount: float) -> None:
    with pytest.raises(ValueError):
        config(deployment_total_spend_usd=amount)


@pytest.mark.parametrize(
    "body",
    [
        {"max_tokens": -1},
        {"max_tokens": "100"},
        {"max_tokens": 1.5},
        {"messages": [{"role": "user", "content": [{"type": "input_audio", "input_audio": {"data": "fake"}}]}]},
    ],
)
def test_unbounded_inputs_are_refused_before_sending(tmp_path: Path, body: dict) -> None:
    store = GatewayStore(tmp_path)
    adapter = Adapter()
    budget = InferenceBudget(config(), store, lambda: NOW)
    with pytest.raises(UpstreamError):
        asyncio.run(BudgetedAdapter(adapter, budget).complete(request(**body)))
    assert adapter.sends == 0 and budget.snapshot()["held_usd"] == 0
    store.close()


def test_images_are_reserved_at_their_token_allowance_not_their_bytes(tmp_path: Path) -> None:
    store = GatewayStore(tmp_path)
    budget = InferenceBudget(config(deployment_image_input_tokens=4096), store, lambda: NOW)
    photo = "data:image/jpeg;base64," + "A" * 2_000_000  # a large encoding; its bytes are not its tokens
    text_only = request()
    with_photo = request(messages=[{"role": "user", "content": [
        {"type": "text", "text": "Help me with algebra."}, {"type": "image_url", "image_url": {"url": photo}},
    ]}])  # fmt: skip
    _, sent = budget.reserve(with_photo)
    assert sent.body["messages"][0]["content"][1]["image_url"]["url"] == photo  # the image itself is sent unchanged
    held_photo = budget.snapshot()["held_usd"]
    budget.reserve(text_only)
    held_text = budget.snapshot()["held_usd"] - held_photo
    price = config().prices["muse-spark-1.3"]
    # The photo adds its allowance (plus the content-list framing), far below what 2 MB of bytes would cost.
    assert 4096 * price.input / 1e6 <= held_photo - held_text < 4500 * price.input / 1e6
    store.close()


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("status", [401, 403, 429])
def test_calls_refused_before_processing_release_their_hold(tmp_path: Path, stream: bool, status: int) -> None:
    from cloud_gateway.config import ProviderSpec
    from cloud_gateway.custody import Secret
    from cloud_gateway.providers.meta import MetaAdapter

    store = GatewayStore(tmp_path)
    budget = InferenceBudget(config(), store, lambda: NOW)
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(status, json={"error": {}})))
    spec = ProviderSpec.model_validate(load_config().providers["meta"].model_dump())
    adapter = BudgetedAdapter(MetaAdapter(spec, Secret("synthetic-key"), client), budget)

    async def call() -> None:
        if stream:
            async for _ in adapter.stream(request()):
                pass
        else:
            await adapter.complete(request())

    with pytest.raises(UpstreamError):
        asyncio.run(call())
    assert budget.snapshot() == {"spent_usd": 0, "today_usd": 0, "held_usd": 0}
    store.close()


def test_a_missing_key_holds_nothing_but_a_server_error_keeps_its_bound(tmp_path: Path) -> None:
    from cloud_gateway.custody import Secret
    from cloud_gateway.providers.meta import MetaAdapter

    store = GatewayStore(tmp_path)
    budget = InferenceBudget(config(), store, lambda: NOW)
    spec = load_config().providers["meta"]
    keyless = BudgetedAdapter(MetaAdapter(spec, None, httpx.AsyncClient()), budget)
    with pytest.raises(UpstreamError, match="no provider key"):
        asyncio.run(keyless.complete(request()))
    assert budget.snapshot()["held_usd"] == 0
    failing = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500, json={"error": {}})))
    server_error = BudgetedAdapter(MetaAdapter(spec, Secret("synthetic-key"), failing), budget)
    with pytest.raises(UpstreamError):
        asyncio.run(server_error.complete(request()))
    assert budget.snapshot()["held_usd"] > 0  # it may have been processed: the bound stays until reconciled
    assert budget.release_held("failed", 0, apply=True)[0] == 1 and budget.snapshot()["held_usd"] == 0
    store.close()


# --- Hold outcomes and targeted release ------------------------------------------------------------------------------


def holds_rows(store: GatewayStore) -> list[dict]:
    with store._lock:
        cursor = store._db.execute("SELECT * FROM inference_budget_holds")
        names = [c[0] for c in cursor.description]
        return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def meta_adapter(budget: InferenceBudget, respond) -> BudgetedAdapter:
    from cloud_gateway.custody import Secret
    from cloud_gateway.providers.meta import MetaAdapter

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    return BudgetedAdapter(MetaAdapter(load_config().providers["meta"], Secret("synthetic-key"), client), budget)


async def call(adapter: BudgetedAdapter, stream: bool, role: str = "solver") -> None:
    sent = replace(request(), role=role)
    if stream:
        async for _ in adapter.stream(sent):
            pass
    else:
        await adapter.complete(sent)


def test_a_hold_records_time_role_model_and_outcome_but_no_payload(tmp_path: Path) -> None:
    store = GatewayStore(tmp_path)
    budget = InferenceBudget(config(), store, lambda: NOW)
    asyncio.run(call(BudgetedAdapter(Adapter(), budget), stream=False, role="checker"))
    [row] = holds_rows(store)
    assert row["created_at"] == NOW and row["role"] == "checker" and row["model"] == "muse-spark-1.3"
    assert row["outcome"] == "settled" and row["spent_micros"] == 48 and not row["migrated"]
    stored = repr(holds_rows(store))
    assert "algebra" not in stored and "fake-session-pseudonym" not in stored  # no prompt, no pseudonym
    store.close()


def raise_timeout(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("synthetic", request=request)


def raise_network(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("synthetic", request=request)


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize(
    ("respond", "outcome", "status", "held"),
    [
        # SPEC §16 records Meta's 400s (e.g. a recursive tool schema) but not whether they bill: keep and say so.
        (lambda r: httpx.Response(400, json={"error": {"param": "parameters"}}), "failed_unbilled_unknown", 400, True),
        (lambda r: httpx.Response(402, json={"error": {}}), "failed_unbilled_unknown", 402, True),
        (lambda r: httpx.Response(429, json={"error": {}}), "unbilled", None, False),
        (lambda r: httpx.Response(401, json={"error": {}}), "unbilled", None, False),
        (lambda r: httpx.Response(500, json={"error": {}}), "failed_other", 500, True),
        (lambda r: httpx.Response(504, json={"error": {}}), "timed_out", 504, True),
        (raise_timeout, "timed_out", None, True),
        (raise_network, "failed_other", None, True),
    ],
    ids=["400", "402", "429", "401", "500", "504", "read-timeout", "network"],
)
def test_each_failure_records_its_outcome(tmp_path: Path, stream: bool, respond, outcome, status, held) -> None:
    store = GatewayStore(tmp_path)
    budget = InferenceBudget(config(), store, lambda: NOW)
    with pytest.raises(UpstreamError):
        asyncio.run(call(meta_adapter(budget, respond), stream))
    [row] = holds_rows(store)
    assert (row["outcome"], row["status"]) == (outcome, status)
    assert (budget.snapshot()["held_usd"] > 0) is held and budget.snapshot()["spent_usd"] == 0
    assert (row["released_at"] is None) is held
    store.close()


def test_cancelled_calls_and_closed_streams_are_marked_cancelled(tmp_path: Path) -> None:
    store = GatewayStore(tmp_path)
    budget = InferenceBudget(config(), store, lambda: NOW)
    gate = asyncio.Event()

    class Hanging(Adapter):
        async def complete(self, request: ProviderRequest) -> ProviderReply:
            await gate.wait()
            raise AssertionError("never reached")

    async def run() -> None:
        with pytest.raises(asyncio.TimeoutError):  # the engine's auxiliary 3 s timeout, in miniature
            await asyncio.wait_for(BudgetedAdapter(Hanging(), budget).complete(request()), 0.01)
        stream = BudgetedAdapter(Adapter(), budget).stream(request())
        await anext(stream)
        await stream.aclose()

    asyncio.run(run())
    assert [row["outcome"] for row in holds_rows(store)] == ["cancelled", "cancelled"]
    assert budget.snapshot()["held_usd"] > 0
    store.close()


@pytest.mark.parametrize("stream", [False, True])
def test_a_call_without_usage_is_marked_no_usage(tmp_path: Path, stream: bool) -> None:
    store = GatewayStore(tmp_path)
    budget = InferenceBudget(config(), store, lambda: NOW)
    asyncio.run(call(BudgetedAdapter(Adapter(usage=Usage()), budget), stream))
    assert [row["outcome"] for row in holds_rows(store)] == ["no_usage"]
    assert budget.snapshot()["held_usd"] > 0
    store.close()


def failed_and_live(tmp_path: Path, clock: list[float]) -> tuple[GatewayStore, InferenceBudget, str]:
    """One 400 hold, one timed-out hold, and one call still in flight."""
    store = GatewayStore(tmp_path)
    budget = InferenceBudget(config(), store, lambda: clock[0])
    with pytest.raises(UpstreamError):
        asyncio.run(call(meta_adapter(budget, lambda r: httpx.Response(400, json={"error": {}})), False))
    with pytest.raises(UpstreamError):
        asyncio.run(call(meta_adapter(budget, raise_timeout), False))
    live, _ = budget.reserve(replace(request(), role="coach"))
    return store, budget, live


def test_release_is_a_dry_run_by_default_and_never_touches_a_call_in_flight(tmp_path: Path) -> None:
    clock = [NOW]
    store, budget, live = failed_and_live(tmp_path, clock)
    held = budget.snapshot()["held_usd"]
    one = held / 3  # the three holds are the same size
    assert budget.release_held("failed", 600) == (0, 0)  # too recent
    clock[0] += 601
    count, usd = budget.release_held("failed", 600)
    assert count == 1 and usd == pytest.approx(one, abs=1e-6)
    assert budget.snapshot()["held_usd"] == held  # dry run: nothing changed
    assert budget.release_held("ended", 0) == (2, pytest.approx(2 * one, abs=1e-6))
    assert budget.release_held("failed", 0, status=500) == (0, 0)
    assert budget.release_held("failed", 0, status=400, apply=True)[0] == 1
    assert budget.release_held("ended", 0, apply=True)[0] == 1  # the timed-out one
    assert budget.release_held("ended", 0, apply=True) == (0, 0)
    assert budget.snapshot()["held_usd"] == pytest.approx(one, abs=1e-6)  # only the call in flight is held
    with pytest.raises(ValueError):
        budget.release_held("in_flight", 0, apply=True)
    [row] = [row for row in holds_rows(store) if row["id"] == live]
    assert row["outcome"] == "in_flight" and row["released_at"] is None
    store.close()


def test_a_release_racing_an_in_flight_call_cannot_lose_its_spend(tmp_path: Path) -> None:
    """The release runs on another connection (as the CLI does) while the call is between send and reply."""
    store = GatewayStore(tmp_path)
    budget = InferenceBudget(config(), store, lambda: NOW + 3600)
    with pytest.raises(UpstreamError):  # one failed hold the release may take
        asyncio.run(call(meta_adapter(budget, lambda r: httpx.Response(400, json={"error": {}})), False))
    sent, released = asyncio.Event(), []

    class Slow(Adapter):
        async def complete(self, request: ProviderRequest) -> ProviderReply:
            sent.set()
            await asyncio.sleep(0.05)
            return await super().complete(request)

    def operator() -> None:
        connection = GatewayStore(tmp_path)
        try:
            cli = InferenceBudget(config(), connection, lambda: NOW + 7200)
            for selector in RELEASABLE:
                released.append(cli.release_held(selector, 0, apply=True))
        finally:
            connection.close()

    async def run() -> None:
        task = asyncio.create_task(BudgetedAdapter(Slow(), budget).complete(request()))
        await sent.wait()
        await asyncio.to_thread(operator)
        await task

    asyncio.run(run())
    assert sum(count for count, _ in released) == 1  # the failed hold only
    assert budget.snapshot() == {"spent_usd": 0.000048, "today_usd": 0.000048, "held_usd": 0}
    store.close()


def test_releases_and_settles_from_many_connections_never_lose_spend(tmp_path: Path) -> None:
    store = GatewayStore(tmp_path)
    InferenceBudget(config(), store, lambda: NOW)
    store.close()

    def worker(index: int) -> int:
        connection = GatewayStore(tmp_path)
        try:
            budget = InferenceBudget(config(), connection, lambda: NOW)
            if index % 2:
                return sum(budget.release_held("ended", 0, apply=True)[0] for _ in range(20))
            for _ in range(20):
                key, bounded = budget.reserve(request())
                budget.settle(key, bounded, Usage(100, 20))
            return 0
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(worker, range(8))) == 0  # nothing ended unsettled, so nothing was released
    reopened = GatewayStore(tmp_path)
    budget = InferenceBudget(config(), reopened, lambda: NOW)
    assert budget.snapshot() == {"spent_usd": pytest.approx(80 * 0.000048), "today_usd": pytest.approx(80 * 0.000048),
                                 "held_usd": 0}  # fmt: skip
    reopened.close()


def test_a_settle_after_its_hold_was_released_still_records_the_spend_once(tmp_path: Path) -> None:
    store = GatewayStore(tmp_path)
    budget = InferenceBudget(config(), store, lambda: NOW)
    key, bounded = budget.reserve(request())
    budget.fail(key, UpstreamError("timeout"))
    assert budget.release_held("timed_out", 0, apply=True)[0] == 1
    budget.settle(key, bounded, Usage(100, 20))
    budget.settle(key, bounded, Usage(100, 20))
    assert budget.snapshot() == {"spent_usd": 0.000048, "today_usd": 0.000048, "held_usd": 0}
    store.close()


def legacy_ledger(tmp_path: Path, holds: list[tuple[str, int]]) -> None:
    """A ledger as the gateway wrote it before holds recorded outcomes."""
    store = GatewayStore(tmp_path)
    store._db.executescript(
        "CREATE TABLE inference_budget_days (day TEXT PRIMARY KEY, spent_micros INTEGER NOT NULL);"
        "CREATE TABLE inference_budget_pending (id TEXT PRIMARY KEY, reserved_micros INTEGER NOT NULL);"
        "CREATE TABLE inference_budget_state (singleton INTEGER PRIMARY KEY CHECK(singleton=1));"
        "INSERT INTO inference_budget_state VALUES (1);"
    )
    with store._tx() as db:
        db.executemany("INSERT INTO inference_budget_pending VALUES (?,?)", holds)
    store.close()


def test_existing_holds_migrate_as_unknown_and_are_released_only_by_name(tmp_path: Path) -> None:
    legacy_ledger(tmp_path, [("solver-400", 83_106), ("aux-cancelled", 17_882)])
    clock = [NOW]
    store = GatewayStore(tmp_path)
    budget = InferenceBudget(config(), store, lambda: clock[0])
    assert budget.snapshot()["held_usd"] == 0.100988  # nothing dropped by the migration
    assert {(r["id"], r["outcome"], r["migrated"], r["created_at"]) for r in holds_rows(store)} == {
        ("solver-400", "unknown", 1, NOW),
        ("aux-cancelled", "unknown", 1, NOW),
    }
    clock[0] += 3600
    for selector in ("failed", "ended", "cancelled", "timed_out"):
        assert budget.release_held(selector, 0) == (0, 0)
    assert budget.release_held("unknown", 7200) == (0, 0)  # the migration dates them: no older than that
    assert budget.release_held("unknown", 600) == (2, 0.100988)
    # An older gateway still running against the same file adds a hold the new code has not seen.
    with store._tx() as db:
        db.execute("INSERT INTO inference_budget_pending VALUES ('old-process', 1000)")
    assert [g["outcome"] for g in budget.holds()] == ["unknown"] and budget.holds()[0]["count"] == 3
    assert budget.release_held("unknown", 0, apply=True)[0] == 2  # not dated yet, so not selected
    InferenceBudget(config(), store, lambda: clock[0])  # the next start dates it
    assert budget.release_held("unknown", 0) == (1, 0.001)
    store.close()


def test_purge_drops_resolved_outcomes_but_never_a_hold_still_counted(tmp_path: Path) -> None:
    store = GatewayStore(tmp_path)
    budget = InferenceBudget(config(), store, lambda: NOW)
    asyncio.run(call(BudgetedAdapter(Adapter(), budget), stream=False))
    budget.reserve(request())
    budget.purge(NOW + 31 * 86400, 30)
    assert [row["outcome"] for row in holds_rows(store)] == ["in_flight"]
    store.close()


def test_the_command_line_prints_a_dry_run_and_refuses_release_all(tmp_path: Path, capsys) -> None:
    from cloud_gateway import holds

    deployed = Path(__file__).parents[1] / "deploy" / "meta-dev.toml"
    toml = tmp_path / "gateway.toml"
    toml.write_text(deployed.read_text().replace('storage_dir = "~/.jana-meta/gateway"', f'storage_dir = "{tmp_path}"'))
    store = GatewayStore(tmp_path)
    budget = InferenceBudget(load_config(toml), store, lambda: NOW)
    with pytest.raises(UpstreamError):
        asyncio.run(call(meta_adapter(budget, lambda r: httpx.Response(400, json={"error": {}})), False))
    budget.reserve(request())
    held = budget.snapshot()["held_usd"]
    store.close()
    assert holds.main(["--config", str(toml), "--release", "failed", "--older-than", "10m"], lambda: NOW + 601) == 0
    out = capsys.readouterr().out
    assert "failed_unbilled_unknown  solver" in out and "status=400" in out and "in_flight" in out
    assert "would release (dry run; add --apply) 1 holds" in out and f"held ${held:.4f}" in out
    with pytest.raises(SystemExit):
        holds.main(["--config", str(toml), "--release-all"])
    assert "--release-all is gone" in capsys.readouterr().err
    holds.main(["--config", str(toml), "--release", "failed", "--older-than", "10m", "--apply"], lambda: NOW + 601)
    assert "released 1 holds" in capsys.readouterr().out
