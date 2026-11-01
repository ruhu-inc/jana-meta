"""Monthly media admission: shared recording pool, video ceiling, durable and atomic before costly work."""

import asyncio
import base64
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from cloud_gateway.auth import Session
from cloud_gateway.study import Refused
from cloud_gateway.tier import allowance_window
from gateway_stubs import Device, Output, gateway_config, harness


def setup(tmp_path, *, metadata_retention_days=30, **limits):
    config = gateway_config(
        tmp_path, metadata_retention_days=metadata_retention_days, plans={"paid": {"jana_online": {"limits": limits}}}
    )
    h = harness(config)
    return h, h.client._transport.app.state.study


def session(h, account="subscription", seats=1):
    return Session("credential", "licence", account, h.clock(), seats)


def exhausted(work):
    with pytest.raises(Refused) as error:
        work()
    assert (error.value.reason, error.value.status) == ("allowance_exhausted", 429)


def test_recordings_and_videos_share_the_recording_pool_and_seats(tmp_path):
    h, service = setup(tmp_path, recording_hours_per_month=1)
    owner = session(h, seats=2)
    service.reserve_media("recording", owner, 3600000, video=False)
    service.reserve_media("video", replace(owner, credential_id="second-device"), 3600000, video=True)
    exhausted(lambda: service.reserve_media("over", owner, 1, video=False))
    exhausted(lambda: service.reserve_media("over-video", owner, 1, video=True))
    # An unrelated subscription has its own allowance.
    service.reserve_media("other", session(h, account="other"), 3600000, video=True)


def test_video_sublimit_does_not_consume_a_separate_recording_pool(tmp_path):
    h, service = setup(tmp_path, recording_hours_per_month=1, video_minutes_per_month=1)
    owner = session(h)
    service.reserve_media("video", owner, 60000, video=True)
    exhausted(lambda: service.reserve_media("extra-video", owner, 1, video=True))
    service.reserve_media("recording", owner, 3540000, video=False)
    exhausted(lambda: service.reserve_media("extra-recording", owner, 1, video=False))


def test_milliseconds_idempotency_restart_and_short_metadata_retention(tmp_path):
    h, service = setup(tmp_path, video_minutes_per_month=1, metadata_retention_days=1)
    owner = session(h)
    service.reserve_media("first", owner, 59999, video=True)
    service.reserve_media("first", owner, 59999, video=True)
    with pytest.raises(Refused) as conflict:
        service.reserve_media("first", owner, 60000, video=True)
    assert conflict.value.reason == "request_conflict"
    # Reopen the actual SQLite store. Reconstructed services and metadata sweeps cannot forgive active usage.
    h2 = harness(h.config, clock=h.clock)
    restored = h2.client._transport.app.state.study
    h.clock.now += 86400 * 2
    assert h.clock.now < allowance_window(owner.period_start, owner.period_start)[1]
    restored.sweep()
    restored.reserve_media("last-ms", owner, 1, video=True)
    exhausted(lambda: restored.reserve_media("over", owner, 1, video=True))


def test_billing_month_rollover_releases_usage_and_purges_expired_rows(tmp_path):
    h, service = setup(tmp_path, video_minutes_per_month=1)
    h.clock.now = datetime(2026, 1, 31, tzinfo=UTC).timestamp()
    owner = session(h)
    service.reserve_media("january", owner, 60000, video=True)
    h.clock.now = datetime(2026, 2, 28, tzinfo=UTC).timestamp() - 1
    exhausted(lambda: service.reserve_media("too-early", owner, 1, video=True))
    h.clock.now += 1
    service.sweep()
    service.reserve_media("february", owner, 60000, video=True)
    assert service.gw.store._db.execute("SELECT identity FROM study_media_usage").fetchall() == [("february",)]


def test_concurrent_connections_cannot_overbook_the_last_minute(tmp_path):
    h, service = setup(tmp_path, video_minutes_per_month=1)
    second = harness(h.config, clock=h.clock).client._transport.app.state.study
    owner = session(h)

    def admit(pair):
        index, worker = pair
        try:
            worker.reserve_media(str(index), owner, 60000, video=True)
            return "admitted"
        except Refused as error:
            return error.reason

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(admit, enumerate([service, second]))) == ["admitted", "allowance_exhausted"]


async def extract(h, device, info, kind="video", jid="stj_" + "0" * 26):
    raw = json.dumps(info).encode()
    grant = await h.client.post(
        "/v1/study/uploads",
        json={
            "request_id": jid,
            "kind": kind,
            "mime_type": "video/x-matroska",
            "byte_length": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        },
        headers=device.headers(),
    )
    assert grant.status_code == 200, grant.text
    uid = grant.json()["upload_id"]
    part = await h.client.put(
        f"/v1/study/uploads/{uid}/chunks/0",
        json={
            "offset": 0,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "data_base64": base64.b64encode(raw).decode(),
        },
        headers=device.headers(),
    )
    assert part.status_code == 200
    return await h.client.post(
        "/v1/study/extract",
        json={
            "request_id": jid,
            "upload_id": uid,
            "source_id": "src_" + "1" * 26,
            "revision": 1,
            "locale": "en",
        },
        headers=device.headers(),
    )


@pytest.mark.parametrize(
    ("kind", "has_audio", "has_video", "limits"),
    [
        ("recording", True, False, {"recording_hours_per_month": 0}),
        ("video", True, True, {"video_minutes_per_month": 0}),
        ("video", False, True, {"video_minutes_per_month": 0}),
        ("recording", True, True, {"video_minutes_per_month": 0}),  # a mislabeled video cannot bypass the cap
    ],
)
def test_zero_quota_stops_audio_and_silent_video_before_provider_or_frame_work(
    tmp_path, monkeypatch, kind, has_audio, has_video, limits
):
    import cloud_gateway.study_recording as recording

    calls = []

    async def worker(service, data, operation, **fields):
        calls.append(operation)
        assert operation == "recording_info"
        return json.loads(data)

    monkeypatch.setattr(recording, "worker", worker)

    async def run():
        h, service = setup(tmp_path, **limits)
        device = Device()
        await device.login(h.client)
        result = await extract(h, device, {"duration_ms": 10000, "has_audio": has_audio, "has_video": has_video}, kind)
        assert result.status_code == 429, result.text
        assert result.json()["error"]["code"] == "allowance_exhausted"
        assert calls == ["recording_info"] and not h.stubs["meta"].seen
        assert service.gw.store._db.execute("SELECT count(*) FROM study_media_usage").fetchone()[0] == 0

    asyncio.run(run())


def test_failed_provider_attempt_keeps_duration_and_another_device_cannot_retry_around_it(tmp_path, monkeypatch):
    import cloud_gateway.study_recording as recording

    async def worker(service, data, operation, **fields):
        if operation == "recording_info":
            return json.loads(data)
        assert operation == "recording_segment"
        return {"duration_ms": 60000, "start_ms": 0, "end_ms": 60000, "wav_base64": base64.b64encode(b"RIFF").decode()}

    monkeypatch.setattr(recording, "worker", worker)

    async def run():
        h, _ = setup(tmp_path, video_minutes_per_month=1)
        first = Device()
        second = Device(subscription=first.subscription)
        await first.login(h.client)
        await second.login(h.client)
        info = {"duration_ms": 60000, "has_audio": True, "has_video": True}
        h.stubs["meta"].say(Output(error=(503, {"error": {"message": "Unavailable"}})))
        result = await extract(h, first, info)
        assert result.status_code != 200
        assert len(h.stubs["meta"].seen) == 1
        result = await extract(h, second, info, jid="stj_" + "2" * 26)
        assert result.status_code == 429 and result.json()["error"]["code"] == "allowance_exhausted"
        assert len(h.stubs["meta"].seen) == 1

    asyncio.run(run())


def test_completed_extraction_counts_once_and_source_deletion_does_not_refund_it(tmp_path, monkeypatch):
    import cloud_gateway.study_recording as recording

    async def worker(service, data, operation, **fields):
        if operation == "recording_info":
            return json.loads(data)
        if operation == "video_keyframes":
            return {"keyframes": []}
        assert operation == "recording_segment"
        return {"duration_ms": 60000, "start_ms": 0, "end_ms": 60000, "wav_base64": base64.b64encode(b"RIFF").decode()}

    monkeypatch.setattr(recording, "worker", worker)

    async def run():
        h, service = setup(tmp_path, video_minutes_per_month=1)
        device = Device()
        await device.login(h.client)
        h.stubs["meta"].say(Output(text=json.dumps({"text": "A test lecture.", "uncertain": False, "language": "en"})))
        info = {"duration_ms": 60000, "has_audio": True, "has_video": True}
        result = await extract(h, device, info)
        assert result.status_code == 200, result.text
        jid = "stj_" + "0" * 26
        cached = await h.client.post(
            "/v1/study/extract",
            json={
                "request_id": jid,
                "upload_id": next(iter(service.uploads)),
                "source_id": "src_" + "1" * 26,
                "revision": 1,
                "locale": "en",
            },
            headers=device.headers(),
        )
        assert cached.status_code == 200 and cached.json() == result.json()
        assert len(h.stubs["meta"].seen) == 1
        assert service.gw.store._db.execute("SELECT duration_ms FROM study_media_usage").fetchall() == [(60000,)]
        assert (await h.client.delete("/v1/study/requests/" + jid, headers=device.headers())).status_code == 204
        result = await extract(h, device, info, jid="stj_" + "3" * 26)
        assert result.status_code == 429 and result.json()["error"]["code"] == "allowance_exhausted"
        assert len(h.stubs["meta"].seen) == 1

    asyncio.run(run())
