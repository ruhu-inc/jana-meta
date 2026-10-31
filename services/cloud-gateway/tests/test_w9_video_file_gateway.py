"""SPEC §20.4 (W9, JM-D34): a video file at the gateway. The file takes the recording path for its audio; the worker
reports its streams; frame times are chosen (chapter boundaries first, scene changes, one per 30 s, 60 per file);
the stills are read as text in the sandboxed worker after the photo privacy pass and come back as chunks with frame
locators prefixed "On screen at m:ss:"; a screened frame is counted and never returned; a container with no audio
stream yields frames only; a file with no video stream says so, so the device downgrades it to a recording. The
first test runs the real sandboxed worker on a synthetic clip; the others script the worker."""

import asyncio
import base64
import hashlib
import json
import sys
from pathlib import Path

import pytest
from gateway_stubs import Device, Output, gateway_config, harness
from test_m42_study import JID, SID

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "study-worker" / "tests"))
from video_fixture import clip

pytest.importorskip("av")
SCENES = [("Projectile motion", 35), ("R = u^2 sin 2theta / g", 35), ("T = 2 u sin theta / g", 35)]


async def upload(h, device, raw: bytes, kind: str = "video", jid: str = JID):
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
    for offset in range(0, len(raw), 1048576):
        part = raw[offset : offset + 1048576]
        response = await h.client.put(
            f"/v1/study/uploads/{uid}/chunks/{offset // 1048576}",
            json={
                "offset": offset,
                "sha256": hashlib.sha256(part).hexdigest(),
                "data_base64": base64.b64encode(part).decode(),
            },
            headers=device.headers(),
        )
        assert response.status_code == 200
    return uid


def said(text: str) -> Output:
    return Output(text=json.dumps({"text": text, "uncertain": False, "language": "en"}))


def test_a_video_file_is_transcribed_and_its_frames_read_as_text_in_the_real_sandbox(tmp_path):
    async def run():
        h = harness(gateway_config(tmp_path))
        device = Device()
        await device.login(h.client)
        raw = clip(SCENES)
        uid = await upload(h, device, raw)
        h.stubs["meta"].say(said("Projectile motion begins here."), said("Now the range equation."))
        body = {"request_id": JID, "upload_id": uid, "source_id": SID, "revision": 1, "locale": "en", "frames": "auto"}
        result = await h.client.post("/v1/study/extract", json=body, headers=device.headers())
        assert result.status_code == 200, result.text
        value = result.json()
        assert value["has_video"] is True and 104_000 <= value["duration_ms"] <= 106_000
        timed = [c for c in value["chunks"] if c["locator"]["kind"] == "time"]
        framed = [c for c in value["chunks"] if c["locator"]["kind"] == "frame"]
        assert [c["locator"]["start_ms"] for c in timed] == [0, 60_000]
        assert value["chunks"][: len(timed)] == timed  # transcript first, frames after, in time order
        frames = value["frames"]
        assert 2 <= len(frames) <= 4 and frames[0]["at_ms"] == 0
        assert all(f["reason"] == "scene" and f["read_state"] in ("read", "unreadable") for f in frames)
        assert all(f["frame_id"].startswith("frm_") and len(f["frame_id"]) == 30 for f in frames)
        read = {f["frame_id"] for f in frames if f["read_state"] == "read"}
        assert {c["locator"]["frame_id"] for c in framed} == read
        for chunk in framed:
            assert chunk["text"].startswith("On screen at ")
        assert len(h.stubs["meta"].seen) == 2  # two audio segments; no model saw a frame (JM-D34)
        assert all("input_audio" in json.dumps(s.body) for s in h.stubs["meta"].seen)
        assert (await h.client.delete("/v1/study/requests/" + JID, headers=device.headers())).status_code == 204
        for path in tmp_path.rglob("*"):
            if path.is_file():
                assert b"Projectile motion begins" not in path.read_bytes()

    asyncio.run(run())


def test_frame_times_prefer_chapters_then_scenes_one_per_thirty_seconds_and_sixty_per_file():
    from cloud_gateway.study_recording import choose_frame_times

    candidates = [{"at_ms": 5_000, "reason": "scene"}, {"at_ms": 0, "reason": "chapter"},
                  {"at_ms": 20_000, "reason": "scene"}, {"at_ms": 31_000, "reason": "scene"},
                  {"at_ms": 31_000, "reason": "chapter"}, {"at_ms": 90_000, "reason": "scene"}]  # fmt: skip
    assert choose_frame_times(candidates) == [{"at_ms": 0, "reason": "chapter"}, {"at_ms": 31_000, "reason": "chapter"},
                                              {"at_ms": 90_000, "reason": "scene"}]  # fmt: skip
    many = [{"at_ms": i * 30_000, "reason": "scene"} for i in range(100)]
    assert len(choose_frame_times(many)) == 60


def test_screened_frames_are_counted_never_returned_and_a_silent_file_yields_frames_only(tmp_path, monkeypatch):
    import cloud_gateway.study_recording as recording

    calls: list[dict] = []

    async def scripted(service, data, kind, **fields):
        calls.append({"kind": kind, **fields})
        if kind == "recording_info":
            return {"duration_ms": 95_000, "has_audio": False, "has_video": True, "width": 640, "height": 360}
        if kind == "video_keyframes":
            return {"keyframes": [{"at_ms": 0, "reason": "scene"}, {"at_ms": 40_000, "reason": "scene"},
                                  {"at_ms": 75_000, "reason": "scene"}]}  # fmt: skip
        if kind == "video_frames":
            return {"frames": [{"at_ms": 0, "text": None, "screened": True},
                               {"at_ms": 40_000, "text": "R = u^2 sin 2theta / g", "screened": False},
                               {"at_ms": 75_000, "text": "", "screened": False}]}  # fmt: skip
        raise AssertionError(kind)

    monkeypatch.setattr(recording, "worker", scripted)

    async def run():
        h = harness(gateway_config(tmp_path))
        device = Device()
        await device.login(h.client)
        raw = b"RIFF" + b"\0" * 2000  # the scripted worker never decodes it
        uid = await upload(h, device, raw)
        body = {"request_id": JID, "upload_id": uid, "source_id": SID, "revision": 1, "locale": "en"}
        result = await h.client.post("/v1/study/extract", json=body, headers=device.headers())
        assert result.status_code == 200, result.text
        value = result.json()
        assert value["has_video"] is True and value["duration_ms"] == 95_000 and value["unreadable_units"] == []
        assert [f["read_state"] for f in value["frames"]] == ["screened", "read", "unreadable"]
        assert [c["locator"]["kind"] for c in value["chunks"]] == ["frame"]
        assert value["chunks"][0]["text"] == "On screen at 0:40:\nR = u^2 sin 2theta / g"
        assert value["chunks"][0]["locator"]["at_ms"] == 40_000
        assert "screened" not in json.dumps(value["chunks"])
        assert [c["kind"] for c in calls] == ["recording_info", "video_keyframes", "video_frames"]
        assert calls[-1]["at_ms"] == [0, 40_000, 75_000]
        assert len(h.stubs["meta"].seen) == 0  # nothing to transcribe, nothing to a model
        assert value["usage"]["cost_usd"] == 0

    asyncio.run(run())


def test_a_file_with_no_video_stream_is_a_recording_and_frames_none_skips_frames(tmp_path, monkeypatch):
    import cloud_gateway.study_recording as recording

    calls: list[str] = []

    async def scripted(service, data, kind, **fields):
        calls.append(kind)
        if kind == "recording_info":
            return {"duration_ms": 10_000, "has_audio": True,
                    "has_video": fields.get("video", False) or "video" in str(data[:5]),
                    "width": None, "height": None}  # fmt: skip
        if kind == "recording_segment":
            return {
                "duration_ms": 10_000,
                "start_ms": 0,
                "end_ms": 10_000,
                "wav_base64": base64.b64encode(b"RIFF").decode(),
            }
        raise AssertionError(kind)

    monkeypatch.setattr(recording, "worker", scripted)

    async def run():
        h = harness(gateway_config(tmp_path))
        device = Device()
        await device.login(h.client)
        uid = await upload(h, device, b"audio" + b"\0" * 100)
        h.stubs["meta"].say(said("Only sound here."))
        body = {"request_id": JID, "upload_id": uid, "source_id": SID, "revision": 1, "locale": "en"}
        result = await h.client.post("/v1/study/extract", json=body, headers=device.headers())
        assert result.status_code == 200, result.text
        value = result.json()
        assert value["has_video"] is False and value["frames"] == []
        assert [c["locator"]["kind"] for c in value["chunks"]] == ["time"]
        assert calls == ["recording_info", "recording_segment"]  # no keyframe scan, no frames
        assert (await h.client.delete("/v1/study/requests/" + JID, headers=device.headers())).status_code == 204
        calls.clear()
        second = "stj_" + "3" * 26  # a deleted request id stays deleted: the next file is a new request
        uid = await upload(h, device, b"video" + b"\0" * 100, jid=second)
        h.stubs["meta"].say(said("Picture and sound."))
        body = {
            "request_id": second,
            "upload_id": uid,
            "source_id": SID,
            "revision": 1,
            "locale": "en",
            "frames": "none",
        }
        result = await h.client.post("/v1/study/extract", json=body, headers=device.headers())
        assert result.status_code == 200, result.text
        value = result.json()
        assert value["has_video"] is True and value["frames"] == [] and calls == ["recording_info", "recording_segment"]

    asyncio.run(run())
