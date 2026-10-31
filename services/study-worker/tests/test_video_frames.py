"""SPEC §20.9 `services/study-worker/tests/test_video_frames.py` (W9, JM-D34): stream info with `has_video`,
`has_audio`, `width` and `height`; a container with no audio stream (info and frames, no segments); keyframe scene
changes at most one per 30 s; stills read as text after the photo privacy pass (a refused frame is screened, an
unsure reading is no text); the per-call bound. The clip is synthetic; OCR quality is not asserted."""

from __future__ import annotations

import itertools

import pytest
from study_worker import DocumentError
from study_worker.media import FRAMES_PER_CALL, decode, frames_text, keyframe_times
from video_fixture import clip

pytest.importorskip("av")

SCENES = [("Projectile motion", 35), ("R = u^2 sin 2theta / g", 35), ("T = 2 u sin theta / g", 35)]


@pytest.fixture(scope="module")
def lecture() -> bytes:
    return clip(SCENES)


def test_stream_info_says_what_the_container_holds(lecture: bytes) -> None:
    info = decode(lecture, None, 120)
    assert info["has_video"] is True and info["has_audio"] is True
    assert info["width"] == 640 and info["height"] == 360
    assert 104_000 <= info["duration_ms"] <= 106_000


def test_a_container_without_audio_has_info_and_frames_but_no_segments() -> None:
    silent = clip(SCENES[:1], audio=False)
    info = decode(silent, None, 120)
    assert info["has_video"] is True and info["has_audio"] is False
    with pytest.raises(DocumentError, match="unreadable_source"):
        decode(silent, 0, 120, info["duration_ms"])
    assert keyframe_times(silent, 120)[0]["at_ms"] == 0
    # A container with no video stream still transcribes as before (the core downgrades it to a recording).
    audio_only = clip([("", 5)], video=False)
    info = decode(audio_only, None, 120)
    assert info["has_video"] is False and info["has_audio"] is True and info["width"] is None
    assert keyframe_times(audio_only, 120) == []


def test_keyframe_scene_changes_are_at_most_one_per_thirty_seconds(lecture: bytes) -> None:
    found = keyframe_times(lecture, 120)
    assert found[0] == {"at_ms": 0, "reason": "scene"}
    times = [f["at_ms"] for f in found]
    assert times == sorted(times) and all(b - a >= 30_000 for a, b in itertools.pairwise(times))
    # The two board changes (at 35 s and 70 s) each show up at the next keyframe after them; nothing else does.
    assert 2 <= len(found) <= 4
    assert any(35_000 <= t <= 45_000 for t in times) and any(70_000 <= t <= 80_000 for t in times)
    assert keyframe_times(lecture, 120, limit=2) == found[:2]


def test_frames_are_read_as_text_after_the_privacy_pass_and_a_refused_frame_is_screened(
    lecture: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    import perception_worker.image as image

    seen: list[int] = []

    def scripted(png: bytes, **_: object) -> dict[str, object]:
        seen.append(len(png))
        n = len(seen)
        if n == 1:
            return {"refusal": "contains_person", "privacy_available": True, "checks": [], "lines": []}
        if n == 2:
            return {"refusal": None, "ocr_model_version": "test", "lines": [
                {"text": "R = u^2 sin 2theta / g", "confidence": 0.97},
                {"text": "range", "confidence": 0.91}]}  # fmt: skip
        return {"refusal": None, "ocr_model_version": "test", "lines": [{"text": "T = ?", "confidence": 0.4}]}

    monkeypatch.setattr(image, "preprocess", scripted)
    frames = frames_text(lecture, [0, 40_000, 75_000])
    assert frames == [
        {"at_ms": 0, "text": None, "screened": True},
        {"at_ms": 40_000, "text": "R = u^2 sin 2theta / g\nrange", "screened": False},
        {"at_ms": 75_000, "text": "", "screened": False},
    ]
    assert len(seen) == 3 and all(size > 0 for size in seen)  # every still went through the pass as a PNG


def test_the_real_pass_reads_a_board_without_pixels_leaving(lecture: bytes) -> None:
    (frame,) = frames_text(lecture, [40_000])
    assert frame["at_ms"] == 40_000 and frame["screened"] is False and isinstance(frame["text"], str)
    assert set(frame) == {"at_ms", "text", "screened"}  # text only: never an image


def test_frames_per_call_and_moments_are_bounded(lecture: bytes) -> None:
    with pytest.raises(DocumentError, match="invalid_request"):
        frames_text(lecture, list(range(0, (FRAMES_PER_CALL + 1) * 1000, 1000)))
    with pytest.raises(DocumentError, match="invalid_request"):
        frames_text(lecture, [-1])
    with pytest.raises(DocumentError, match=r"unsupported_format|corrupt_source"):
        frames_text(b"not a container at all", [0])
