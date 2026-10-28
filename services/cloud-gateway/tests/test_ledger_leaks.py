"""Calls the caller abandons still reach the spending ledger (SPEC §4.3): a client that disconnects mid-stream, a task
cancelled before the reply, a speech-to-text open cancelled by barge-in or idle, a SAM call cancelled mid-send, and a
gateway that died with holds in flight. Admin routes check the header before touching a secret. No network calls."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import pytest
from cloud_gateway.config import load_config
from cloud_gateway.custody import Secret
from cloud_gateway.inference_budget import InferenceBudget
from cloud_gateway.providers.base import ProviderRequest
from cloud_gateway.speech_fakes import FakeRecognizer, fake_stack
from cloud_gateway.store import GatewayStore
from gateway_stubs import AUDIENCE, Device, FakeSecrets, Output, gateway_config, harness
from starlette.requests import Request
from test_gateway_voc28_cloud_voice import connect, opened, setup
from test_meta_speech import FakeServer, recognizer
from test_sam import jpeg, sam_config

BUDGET = {"device_burst": 1000, "licence_burst": 10000, "deployment_total_spend_usd": 10.0}
QUESTION = "Help me factorise x squared plus five x plus six, step by step please."


def chat_body(stream: bool) -> dict[str, Any]:
    return {"model": "primary/fast-model", "messages": [{"role": "user", "content": QUESTION}], "stream": stream}


def scope(path: str, headers: dict[str, str]) -> dict[str, Any]:
    return {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"}, "http_version": "1.1",
            "method": "POST", "scheme": "https", "path": path, "raw_path": path.encode(), "query_string": b"",
            "root_path": "", "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
            "client": ("127.0.0.1", 50000), "server": (AUDIENCE, 443)}  # fmt: skip


def request(path: str, headers: dict[str, str], body: dict[str, Any]) -> Request:
    """A request whose body arrives at once and whose client then stays connected until it is cancelled."""
    sent = False

    async def receive() -> dict[str, Any]:
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": json.dumps(body).encode(), "more_body": False}
        await asyncio.Event().wait()
        raise AssertionError("never reached")

    return Request(scope(path, {**headers, "content-type": "application/json"}), receive)


def records(gw: Any) -> list[tuple[int, str, int, float]]:
    return gw.store._db.execute("SELECT status, outcome, tokens_in, cost_usd FROM requests").fetchall()


def hold_outcomes(gw: Any) -> list[str]:
    return [row[0] for row in gw.store._db.execute("SELECT outcome FROM inference_budget_holds").fetchall()]


async def until(condition: Any) -> None:
    for _ in range(500):
        if condition():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition never held")


def assert_charged_input_estimate(gw: Any, status: int) -> None:
    """The call is recorded as abandoned, charged at least its input (a token is at least one byte), and its ledger
    hold is replaced by that estimate rather than left counted at the full bound."""
    [(recorded_status, outcome, tokens_in, cost)] = records(gw)
    assert (recorded_status, outcome) == (status, "client_disconnected")
    assert tokens_in >= len(QUESTION) and cost > 0
    assert hold_outcomes(gw) == ["client_disconnected"]
    snapshot = gw.inference_budget.snapshot()
    assert snapshot["held_usd"] == 0 and snapshot["spent_usd"] > 0


# --- 1. chat: a client that goes away ---------------------------------------------------------------------------------


def test_a_client_that_disconnects_mid_stream_is_charged_the_input_estimate(tmp_path: Path) -> None:
    """Uvicorn's path (ASGI 2.3): the disconnect cancels the response task while the gateway awaits the provider."""

    async def run() -> None:
        h = harness(gateway_config(tmp_path, quotas=BUDGET))
        app = h.client._transport.app  # type: ignore[attr-defined]
        device = Device()
        await device.login(h.client)
        h.stubs["meta"].say(Output(text="First, find two numbers.", hang_after=1))
        body, first, sent = json.dumps(chat_body(stream=True)).encode(), asyncio.Event(), False
        chunks: list[bytes] = []

        async def receive() -> dict[str, Any]:
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            await first.wait()
            return {"type": "http.disconnect"}  # barge-in: the device drops the stream after the first words

        async def send(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.body" and message.get("body"):
                chunks.append(message["body"])
                first.set()

        headers = {**device.headers(), "content-type": "application/json"}
        await asyncio.wait_for(app(scope("/v1/chat/completions", headers), receive, send), 5)
        assert chunks and b"First" in chunks[0]
        await asyncio.sleep(0)
        assert_charged_input_estimate(app.state.gateway, 200)
        await h.client.aclose()

    asyncio.run(run())


def test_a_stream_closed_by_its_reader_is_charged_the_input_estimate(tmp_path: Path) -> None:
    """The other way a response ends early: its body iterator is closed at a yield (GeneratorExit)."""

    async def run() -> None:
        h = harness(gateway_config(tmp_path, quotas=BUDGET))
        gw = h.client._transport.app.state.gateway  # type: ignore[attr-defined]
        device = Device()
        await device.login(h.client)
        h.stubs["meta"].say(Output(text="First, find two numbers whose product is six."))
        response = await gw.chat(request("/v1/chat/completions", device.headers(), chat_body(stream=True)))
        events = response.body_iterator
        assert b"First" in await anext(events)
        await events.aclose()
        assert_charged_input_estimate(gw, 200)
        await h.client.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("stream", [False, True], ids=["complete", "stream-before-first-chunk"])
def test_a_cancelled_call_before_the_reply_is_charged_the_input_estimate(tmp_path: Path, stream: bool) -> None:
    async def run() -> None:
        h = harness(gateway_config(tmp_path, quotas=BUDGET))
        gw = h.client._transport.app.state.gateway  # type: ignore[attr-defined]
        device = Device()
        await device.login(h.client)
        h.stubs["meta"].say(Output(text="never sent", hang_after=0))
        call = asyncio.create_task(gw.chat(request("/v1/chat/completions", device.headers(), chat_body(stream))))
        await until(lambda: h.stubs["meta"].seen)
        await asyncio.sleep(0.01)
        call.cancel()
        with pytest.raises(asyncio.CancelledError):
            await call
        assert_charged_input_estimate(gw, 499)
        await h.client.aclose()

    asyncio.run(run())


# --- 2. holds a dead gateway left in flight ---------------------------------------------------------------------------


def test_holds_left_in_flight_by_a_dead_gateway_become_releasable_at_startup(tmp_path: Path) -> None:
    config = load_config(quotas={"deployment_total_spend_usd": 1.0},
                         prices={"muse-spark-1.3": {"input": 0.30, "cached_input": 0.06, "output": 0.90}})  # fmt: skip
    model = config.providers["meta"].models["fast-model"]
    ask = ProviderRequest(model, {"messages": [{"role": "user", "content": QUESTION}]}, "pseudonym")
    clock = [1792716361.0]
    store = GatewayStore(tmp_path)
    crashed = InferenceBudget(config, store, lambda: clock[0])
    orphan, _ = crashed.reserve(ask)
    live, _ = crashed.reserve(ask)
    with store._tx() as db:  # one hold is another gateway's, still running against the same file
        db.execute("UPDATE inference_budget_holds SET pid=? WHERE id=?", (os.getppid(), live))
    held = crashed.snapshot()["held_usd"]
    clock[0] += 600
    InferenceBudget(config, store, lambda: clock[0])  # the operator's command line opens the ledger: nothing changes
    assert [g["outcome"] for g in crashed.holds()] == ["in_flight"]
    assert crashed.release_held("unknown", 0) == (0, 0)  # an in-flight hold is never selectable

    restarted = InferenceBudget(config, store, lambda: clock[0])  # the gateway that made `orphan` is gone
    assert restarted.recover() == 1
    outcomes = dict(store._db.execute("SELECT id, outcome FROM inference_budget_holds").fetchall())
    assert outcomes == {orphan: "unknown", live: "in_flight"}
    assert restarted.snapshot()["held_usd"] == held  # nothing dropped until an operator names it
    assert restarted.release_held("unknown", 300, apply=True) == (1, held / 2)  # dated when it was made
    store.close()


def test_the_gateway_recovers_orphaned_holds_when_it_starts(tmp_path: Path) -> None:
    config = gateway_config(tmp_path, quotas=BUDGET)
    store = GatewayStore(tmp_path)
    InferenceBudget(config, store, lambda: 1_790_000_000.0).reserve(
        ProviderRequest(config.providers["meta"].models["fast-model"], {"messages": []}, "pseudonym")
    )
    store.close()
    gw = harness(config).client._transport.app.state.gateway  # type: ignore[attr-defined]
    assert hold_outcomes(gw) == ["unknown"]


# --- 3. speech to text: an open cancelled by idle, barge-in or close --------------------------------------------------


def test_a_cancelled_speech_to_text_open_releases_its_hold(tmp_path: Path) -> None:
    stack = fake_stack(recognizer=FakeRecognizer(open_delay=30))
    client, device, _, _ = setup(tmp_path, stack, voice_prewarm_s=0.01, voice_connect_timeout_s=30,
                                 quotas=BUDGET)  # fmt: skip
    budget = client.app.state.gateway.inference_budget  # type: ignore[attr-defined]
    with client:
        with connect(client, device) as ws:
            opened(ws)
            assert budget.snapshot()["held_usd"] > 0  # the open holds an hour of Voice Transcribe
        # Closing the connection (or the gateway) cancels the open that never finished.
    store = GatewayStore(tmp_path / "store")
    assert store._db.execute("SELECT count(*) FROM inference_budget_pending").fetchone() == (0,)
    holds = store._db.execute("SELECT role, outcome FROM inference_budget_holds").fetchall()
    assert holds == [("voice_stt", "unbilled")]
    store.close()


def test_a_cancelled_recognizer_handshake_closes_its_socket() -> None:
    server = FakeServer(ack=False)  # the handshake is never acknowledged

    async def run() -> None:
        opening = asyncio.create_task(recognizer(server).open("en"))
        await until(lambda: server.sockets and server.sockets[0].sent)
        opening.cancel()
        with pytest.raises(asyncio.CancelledError):
            await opening

    asyncio.run(run())
    assert server.closed == 1


# --- 4. SAM: a call cancelled mid-send --------------------------------------------------------------------------------


def test_a_cancelled_segmentation_is_charged_and_recorded(tmp_path: Path) -> None:
    async def run() -> None:
        config = sam_config(tmp_path, image_usd=0.0025)
        config = config.model_copy(update={"quotas": config.quotas.model_copy(update=BUDGET)})
        h = harness(config)
        gw = h.client._transport.app.state.gateway  # type: ignore[attr-defined]
        segmenter = h.client._transport.app.state.segment  # type: ignore[attr-defined]
        device = Device()
        await device.login(h.client)
        h.stubs["sam"].say("!hang")
        body = {"image": jpeg(), "width": 90, "height": 50, "concept": "angle label"}
        call = asyncio.create_task(segmenter.handle(request("/v1/vision/segment", device.headers(), body)))
        await until(lambda: h.stubs["sam"].seen)
        await asyncio.sleep(0.01)
        call.cancel()
        with pytest.raises(asyncio.CancelledError):
            await call
        rows = gw.store._db.execute("SELECT feature, status, outcome, cost_usd FROM requests").fetchall()
        assert rows == [("vision_segment", 499, "client_disconnected", 0.0025)]  # the image was sent: it may bill
        assert hold_outcomes(gw) == ["settled"]
        assert gw.inference_budget.snapshot() == {"spent_usd": 0.0025, "today_usd": 0.0025, "held_usd": 0.0}
        await h.client.aclose()

    asyncio.run(run())


# --- 5. admin routes: no secret read for a request without a bearer header --------------------------------------------


class CountingSecrets(FakeSecrets):
    def __init__(self) -> None:
        super().__init__()
        self.asked: list[str] = []

    def get(self, name: str) -> Secret | None:
        self.asked.append(name)
        return super().get(name)


@pytest.mark.parametrize("path", ["/admin/v1/credentials/cred_x/revoke", "/admin/v1/operations/switch"])
def test_an_admin_request_never_reads_a_secret(tmp_path: Path, path: str) -> None:
    """A web page can POST no-cors to the gateway on 127.0.0.1; in development each secret read is a blocking
    keychain lookup. The admin token is read once, at startup, and only compared when a bearer header is present."""
    secrets = CountingSecrets()

    async def run() -> None:
        h = harness(gateway_config(tmp_path), secrets=secrets)
        assert "admin_token" in secrets.asked  # read once, at startup
        secrets.asked.clear()
        plain = {"content-type": "text/plain"}  # what a cross-site no-cors form can send
        assert (await h.client.post(path, content=b"{}", headers=plain)).status_code == 401
        wrong = {"authorization": "Bearer not-the-token"}
        assert (await h.client.post(path, json={}, headers=wrong)).status_code == 401
        right = {"authorization": "Bearer " + secrets.values["admin_token"]}
        assert (await h.client.post(path, json={}, headers=right)).status_code in (400, 404)
        await h.client.aclose()

    asyncio.run(run())
    assert secrets.asked == []
