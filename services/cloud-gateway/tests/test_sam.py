"""SAM 3.1 behind the gateway (JM-D10, SPEC §5): the segment route, the reply's decoding, the budget and the image cap,
and "no match". Every call goes to a stub of Meta's Responses API; no test reaches Meta."""

from __future__ import annotations

import asyncio
import base64
import io
from pathlib import Path
from typing import Any

import pytest
from cloud_gateway.config import load_config
from cloud_gateway.minimise import refusal
from cloud_gateway.providers.base import UpstreamError
from cloud_gateway.providers.sam import ObjectPrompt, decode, object_prompt
from gateway_stubs import FAKE_KEYS, Device, gateway_config, harness
from meta_sam_parser._mask_codec import _encode_raster  # the reference encoder, to build exact test replies
from PIL import Image


def jpeg(width: int = 90, height: int = 50) -> str:
    out = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(out, "JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode()


def ring(width: int, height: int) -> bytes:
    """A mask with a filled centre and an empty border, row-major 0/1."""
    return bytes(int(0 < x < width - 1 and 0 < y < height - 1) for y in range(height) for x in range(width))


def record(oid: int, box: tuple[int, int, int, int], size: tuple[int, int], confidence: float | None = 0.875) -> str:
    """One SAM record as the API writes it: an inclusive box and a one-bit mask covering it."""
    left, top, right, bottom = box
    w, h = right - left, bottom - top
    c = f";c={confidence}" if confidence is not None else ""
    payload = _encode_raster(ring(w, h), w, h)
    return (f"{oid}<|box;x1={left};y1={top};x2={right - 1};y2={bottom - 1};w={size[0]};h={size[1]}{c}|>"
            f"<|mask;x=0;y=0{c};data={h},{w},{payload}|>")  # fmt: skip


def sam_config(tmp_path: Path, **sam: Any):
    defaults = load_config()
    return gateway_config(
        tmp_path,
        slots=dict(defaults.slots),
        providers={"meta": defaults.providers["meta"].model_dump()},
        prices={key: value.model_dump() for key, value in defaults.prices.items()},
        sam={"enabled": True, "base_url": "https://meta.stub/v1", **sam},
    )


async def segment(h, device: Device, body: dict[str, Any]):
    return await h.client.post("/v1/vision/segment", json=body, headers=device.headers())


def test_object_prompts_are_written_in_the_token_grammar_with_inclusive_corners() -> None:
    text = object_prompt(900, 500, [ObjectPrompt(1, (60, 50, 501, 141)),
                                    ObjectPrompt(2, None, ((10, 20, "positive"), (30, 40, "negative")))])  # fmt: skip
    assert text == ("<0f>1<|box;x1=60;y1=50;x2=500;y2=140;w=900;h=500|>,"
                    "2<|point;x=10;y=20;w=900;h=500|>-<|point;x=30;y=40;w=900;h=500|>")  # fmt: skip


def test_decoding_places_each_mask_on_its_box_with_its_confidence() -> None:
    text = "<0f>" + record(1, (77, 70, 390, 114), (900, 500)) + "," + record(2, (5, 6, 15, 12), (900, 500), None)
    first, second = decode(text)
    assert (first.id, first.box, first.confidence) == ("1", (77, 70, 390, 114), 0.875)
    assert first.mask == ring(313, 44) and len(first.mask) == first.width * first.height
    assert (second.id, second.box, second.confidence) == ("2", (5, 6, 15, 12), None)  # no `c`: unknown, not zero
    runs = second.runs()
    assert sum(runs) == 10 * 6 and runs[0] == 11  # the top row and the next row's first pixel are empty


def test_empty_output_is_no_match_and_garbage_is_a_bad_response() -> None:
    assert decode("") == () and decode("  \n") == ()
    with pytest.raises(UpstreamError) as raised:
        decode("I cannot help with that.")
    assert raised.value.reason == "bad_response"


def test_a_mask_that_does_not_decode_is_dropped_not_guessed() -> None:
    good = record(1, (0, 0, 10, 10), (90, 50))
    broken = good.replace("data=10,10,!", "data=10,10,!!!!!!")
    assert decode("<0f>" + broken) == ()


def test_segment_route_sends_box_prompts_and_returns_masks_as_runs(tmp_path: Path) -> None:
    async def run() -> None:
        h = harness(sam_config(tmp_path))
        device = Device()
        await device.login(h.client)
        h.stubs["sam"].say("<0f>" + record(1, (10, 5, 40, 25), (90, 50)))
        image = jpeg()
        reply = await segment(h, device, {"image": image, "width": 90, "height": 50,
                                          "objects": [{"id": 1, "box": [8, 4, 44, 28]}]})  # fmt: skip
        assert reply.status_code == 200, reply.text
        body = reply.json()
        assert body["images"] == 1
        (found,) = body["objects"]
        assert found["id"] == "1" and found["box"] == [10, 5, 40, 25] and found["confidence"] == 0.875
        assert found["mask"]["width"] == 30 and found["mask"]["height"] == 20 and sum(found["mask"]["runs"]) == 600
        sent = h.stubs["sam"].seen[-1]
        assert sent["model"] == "sam-3.1" and sent["store"] is False
        assert sent["metadata"] == {"mask_encoding": "one_bit", "include_confidence": "true"}
        text, picture = sent["input"][0]["content"]
        assert text == {"type": "input_text", "text": "<0f>1<|box;x1=8;y1=4;x2=43;y2=27;w=90;h=50|>"}
        assert picture == {"type": "input_image", "image_url": image}
        assert h.stubs["sam"].headers[-1]["authorization"] == f"Bearer {FAKE_KEYS['meta_api_key']}"
        assert FAKE_KEYS["meta_api_key"] not in reply.text
        await h.client.aclose()

    asyncio.run(run())


def test_a_concept_is_sent_alone_and_no_match_is_an_empty_list(tmp_path: Path) -> None:
    async def run() -> None:
        h = harness(sam_config(tmp_path))
        device = Device()
        await device.login(h.client)
        h.stubs["sam"].say("")
        reply = await segment(h, device, {"image": jpeg(), "width": 90, "height": 50, "concept": "force arrow"})
        assert reply.status_code == 200 and reply.json() == {"objects": [], "images": 1}
        assert h.stubs["sam"].seen[-1]["input"][0]["content"][0]["text"] == "force arrow"
        await h.client.aclose()

    asyncio.run(run())


@pytest.mark.parametrize(
    "body",
    [
        {"concept": "force arrow", "objects": [{"id": 1, "box": [0, 0, 5, 5]}]},  # both
        {},  # neither
        {"objects": [{"id": i, "box": [0, 0, 5, 5]} for i in range(17)]},  # over 16
        {"objects": [{"id": 1, "box": [0, 0, 91, 5]}]},  # outside the image
        {"objects": [{"id": 1, "box": [5, 5, 5, 9]}]},  # empty
        {"objects": [{"id": 1}]},  # no prompt
        {"concept": "bus, bicycle"},  # a list of concepts returns nothing upstream
        {"concept": "force arrow", "extra": 1},
    ],
)
def test_malformed_requests_are_refused_before_meta_sees_them(tmp_path: Path, body: dict[str, Any]) -> None:
    async def run() -> None:
        h = harness(sam_config(tmp_path))
        device = Device()
        await device.login(h.client)
        reply = await segment(h, device, {"image": jpeg(), "width": 90, "height": 50, **body})
        assert reply.status_code == 400, reply.text
        assert h.stubs["sam"].seen == []
        await h.client.aclose()

    asyncio.run(run())


def test_auth_pseudonym_and_minimisation_hold_on_the_segment_route(tmp_path: Path) -> None:
    async def run() -> None:
        h = harness(sam_config(tmp_path))
        device = Device()
        await device.login(h.client)
        body = {"image": jpeg(), "width": 90, "height": 50, "concept": "force arrow"}
        assert (await h.client.post("/v1/vision/segment", json=body)).status_code == 401
        no_pseudonym = {"Authorization": f"Bearer {device.token}"}
        assert (await h.client.post("/v1/vision/segment", json=body, headers=no_pseudonym)).status_code == 400
        profile = {**body, "concept": "prf_abcdef"}
        assert (await segment(h, device, profile)).status_code in (400, 422)
        assert h.stubs["sam"].seen == []
        await h.client.aclose()

    asyncio.run(run())


def test_image_bytes_that_spell_a_profile_id_are_not_refused() -> None:
    # About a quarter of photos contain `prf` in their base64 (SPEC §17, W2): image bytes are not words.
    image = "data:image/jpeg;base64,/9j/4AAQprfABCDEFGH" + "A" * 40
    assert (
        refusal({}, {"messages": [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": image}}]}]})
        is None
    )
    assert refusal({}, {"messages": [{"role": "user", "content": "my id is prf_ABCDEFGH"}]}) is not None


def test_each_image_is_billed_to_the_budget_at_the_per_image_price(tmp_path: Path) -> None:
    async def run() -> None:
        h = harness(sam_config(tmp_path, image_usd=0.0025))
        gw = h.client._transport.app.state.gateway  # type: ignore[attr-defined]
        device = Device()
        await device.login(h.client)
        h.stubs["sam"].say("", "")
        body = {"image": jpeg(), "width": 90, "height": 50, "concept": "angle label"}
        assert (await segment(h, device, body)).status_code == 200
        assert (await segment(h, device, body)).status_code == 200
        rows = gw.store._db.execute("SELECT feature, model, cost_usd FROM requests").fetchall()
        assert rows == [("vision_segment", "sam-3.1", 0.0025)] * 2
        await h.client.aclose()

    asyncio.run(run())


def test_the_shared_inference_budget_holds_and_settles_each_image(tmp_path: Path) -> None:
    async def run() -> None:
        h = harness(gateway_config(tmp_path, **_budgeted()))
        gw = h.client._transport.app.state.gateway  # type: ignore[attr-defined]
        device = Device()
        await device.login(h.client)
        h.stubs["sam"].say("", "")
        body = {"image": jpeg(), "width": 90, "height": 50, "concept": "angle label"}
        assert (await segment(h, device, body)).status_code == 200
        assert gw.inference_budget.snapshot() == {"spent_usd": 0.4, "today_usd": 0.4, "held_usd": 0.0}
        over = await segment(h, device, body)  # 0.8 would pass the $0.50 daily cap
        assert over.status_code == 429 and over.json()["error"]["code"] == "insufficient_quota"  # as chat answers it
        assert len(h.stubs["sam"].seen) == 1  # refused before Meta saw it
        assert gw.inference_budget.snapshot()["held_usd"] == 0.0
        await h.client.aclose()

    asyncio.run(run())


def _budgeted() -> dict[str, Any]:
    defaults = load_config()
    return {
        "slots": dict(defaults.slots),
        "providers": {"meta": defaults.providers["meta"].model_dump()},
        "prices": {key: value.model_dump() for key, value in defaults.prices.items()},
        "sam": {"enabled": True, "base_url": "https://meta.stub/v1", "image_usd": 0.4},
        "quotas": {
            "device_burst": 1000,
            "licence_burst": 10000,
            "deployment_daily_spend_usd": 0.5,
            "device_daily_spend_usd": 100.0,
        },
    }


def test_the_image_cap_counts_every_send_and_refuses_past_it(tmp_path: Path) -> None:
    async def run() -> None:
        h = harness(sam_config(tmp_path, total_images=2))
        device = Device()
        await device.login(h.client)
        h.stubs["sam"].say("", (500, {"error": {"message": "boom", "type": "server_error"}}), "")
        body = {"image": jpeg(), "width": 90, "height": 50, "concept": "angle label"}
        assert (await segment(h, device, body)).status_code == 200
        failed = await segment(h, device, body)
        assert failed.status_code >= 500  # a server error may have been billed: it stays counted
        capped = await segment(h, device, body)
        assert capped.status_code == 429 and capped.json()["error"]["code"] == "quota_exceeded"
        assert len(h.stubs["sam"].seen) == 2
        await h.client.aclose()

    asyncio.run(run())


def test_a_refused_key_does_not_use_up_an_image(tmp_path: Path) -> None:
    async def run() -> None:
        h = harness(sam_config(tmp_path, total_images=1))
        device = Device()
        await device.login(h.client)
        h.stubs["sam"].say((401, {"error": {"message": "bad key", "type": "invalid_api_key"}}), "")
        body = {"image": jpeg(), "width": 90, "height": 50, "concept": "angle label"}
        assert (await segment(h, device, body)).status_code >= 400
        assert (await segment(h, device, body)).status_code == 200  # the 401 billed nothing and counted nothing
        await h.client.aclose()

    asyncio.run(run())


def test_segmentation_off_or_without_a_key_is_unavailable(tmp_path: Path) -> None:
    async def run() -> None:
        h = harness(sam_config(tmp_path, enabled=False))
        device = Device()
        await device.login(h.client)
        reply = await segment(h, device, {"image": jpeg(), "width": 90, "height": 50, "concept": "angle label"})
        assert reply.status_code == 503 and reply.json()["error"]["code"] == "provider_unavailable"
        await h.client.aclose()

    asyncio.run(run())


def test_shipped_defaults_price_sam_and_cap_it_for_the_event() -> None:
    sam = load_config().sam
    assert sam.enabled and sam.model == "sam-3.1" and sam.base_url == "https://api.meta.ai/v1"
    assert sam.image_usd == 0.0025 and sam.total_images == 300 and sam.max_prompts == 16
    assert sam.secret == "meta_api_key"  # noqa: S105 -- the secret's name, not a key
