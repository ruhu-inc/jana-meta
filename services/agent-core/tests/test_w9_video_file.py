"""SPEC §20.9 `test_w9_video_file.py` (W9, JM-D34): a dropped .mp4 is kind `video` by suffix (an older client's
`recording` still works); the frames choice is kept on the source; the extracted revision downgrades the source to a
recording when the container had no video stream; frames come back as text chunks with frame locators and as
`study_frames` rows, a screened frame counted and never read; a quiz item cites a frame locator; the player is served
the file; and the rows go with the source (retention rule, profile store, inventory, migration v23). Synthetic data."""

from __future__ import annotations

import asyncio
import base64
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from agent_core.contracts import errors
from agent_core.engine.study import StudyError, StudyQueue, digest
from agent_core.net.study import Extracted
from agent_core.store.generated.schema import LEARNER
from agent_core.store.profile_stores import PROFILE_STORES
from agent_core.store.retention import RULES
from agent_core.store.sqlite import open_database
from test_w8_study_activity import World, world

MP4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2mp41" + b"\x00" * 200
FRAME_READ, FRAME_SCREENED, FRAME_BLANK = ("frm_" + "A" * 26, "frm_" + "B" * 26, "frm_" + "C" * 26)
TRANSCRIPT = [
    {"locator": {"kind": "time", "start_ms": 0, "end_ms": 60000}, "text": "Today we derive the range equation."},
    {"locator": {"kind": "time", "start_ms": 60000, "end_ms": 95000}, "text": "The range depends on sin two theta."},
]
FRAMES = [
    {"frame_id": FRAME_SCREENED, "at_ms": 0, "reason": "scene", "read_state": "screened"},
    {"frame_id": FRAME_READ, "at_ms": 40000, "reason": "scene", "read_state": "read"},
    {"frame_id": FRAME_BLANK, "at_ms": 75000, "reason": "chapter", "read_state": "unreadable"},
]
FRAME_UNIT = {"locator": {"kind": "frame", "at_ms": 40000, "frame_id": FRAME_READ},
              "text": "On screen at 0:40:\nR = u^2 sin 2theta / g"}  # fmt: skip


class Cloud:
    """The gateway as the device sees it: an extraction with frames, and a quiz whose first item cites a frame."""

    def __init__(self, has_video: bool = True, frames: bool = True) -> None:
        self.has_video, self.frames = has_video, frames
        self.extracted: list[dict[str, Any]] = []
        self.processed: list[dict[str, Any]] = []

    async def extract(self, conn: Any, jid: str, request: dict[str, Any], source: dict[str, Any], data: bytes) -> Any:
        self.extracted.append({"request": request, "source": dict(source), "bytes": len(data)})
        units = Extracted(
            [dict(u, ocr=True) for u in TRANSCRIPT]
            + ([dict(FRAME_UNIT, ocr=True)] if self.frames and self.has_video else [])
        )
        units.frames = list(FRAMES) if self.frames and self.has_video else []
        units.has_video = self.has_video
        return units

    async def cleanup(self, conn: Any) -> None:
        return None

    async def process(self, conn: Any, jid: str, request: dict[str, Any], chunks: list[dict[str, Any]], attempt: int,
                      batch_index: int = 0) -> dict[str, Any]:  # fmt: skip
        self.processed.append(request)
        frame = next(c for c in chunks if c["locator"]["kind"] == "frame")
        first, line = [c for c in chunks if c["locator"]["kind"] == "time"][:2]

        def span(chunk: dict[str, Any], quote: str, text: str) -> dict[str, Any]:
            start = chunk["text"].index(quote)
            return {"text": text, "citations": [{"source_id": chunk["source_id"], "revision": chunk["revision"],
                                                 "chunk_id": chunk["chunk_id"], "start": start,
                                                 "end": start + len(quote), "quote": quote}]}  # fmt: skip

        quiz = {
            "items": [{"item_id": "a", "type": "true_false",
                       "stem": span(frame, "R = u^2 sin 2theta / g",
                                    "The board gives the range as R = u^2 sin 2theta / g.")},
                      {"item_id": "b", "type": "true_false", "stem": span(line, "The range depends on sin two theta.",
                                                                           "The range depends on sin two theta.")}],
            "keys": [{"item_id": "a", "answer": "true", "marking": "judged",
                      "explanation": span(frame, "R = u^2 sin 2theta / g", "It is written on the board.")},
                     {"item_id": "b", "answer": "true", "marking": "judged",
                      "explanation": span(line, "The range depends on sin two theta.", "As the lecture says.")}],
        }  # fmt: skip
        return {"request_id": jid, "kind": "quiz",
                "claims": [span(first, "Today we derive", "The lecture derives the range.")],
                "quiz": quiz}  # fmt: skip


def video_source(w: World, name: str = "lecture.mp4", **extra: Any) -> dict[str, Any]:
    source = w.desk.create({"kind": "video", "file_name": name, "mime_type": "video/mp4", "byte_length": len(MP4),
                            "sha256": digest(MP4), **extra})  # fmt: skip
    w.desk.upload(
        source["source_id"], 0, {"offset": 0, "sha256": digest(MP4), "data_base64": base64.b64encode(MP4).decode()}
    )
    return w.desk.source(source["source_id"])


def extract(w: World, source: dict[str, Any], cloud: Cloud) -> dict[str, Any]:
    job = w.desk.create_job({"kind": "extract", "execution": "prefer_cloud",
                             "sources": [{"source_id": source["source_id"],
                                          "revision": source["revision"]}]})  # fmt: skip
    queue = StudyQueue(lambda: w.conn, lambda: None, lambda: False, w.clock, w.desk.settings)
    queue.cloud = cloud
    asyncio.run(queue.run(w.desk, job["job_id"]))
    done = w.desk.job(job["job_id"])
    assert done["state"] == "completed", done
    return w.desk.source(source["source_id"])


def test_a_dropped_mp4_is_a_video_source_by_suffix_and_keeps_its_frames_choice(tmp_path: Path) -> None:
    w = world(tmp_path)
    source = video_source(w)
    assert source["kind"] == "video" and source["state"] == "queued" and source["frames_choice"] == "auto"
    assert errors("study/workspace#/$defs/Source", source) == []
    none = video_source(w, name="screen.webm", frames="none")
    assert none["frames_choice"] == "none"
    with pytest.raises(StudyError, match="unsupported_format"):
        w.desk.create(
            {
                "kind": "video",
                "file_name": "talk.wav",
                "mime_type": "audio/wav",
                "byte_length": 10,
                "sha256": digest(b"x"),
            }
        )
    # An older client still names an .mp4 a recording: accepted as before (the audio path, no frames).
    older = w.desk.create(
        {
            "kind": "recording",
            "file_name": "old.mp4",
            "mime_type": "video/mp4",
            "byte_length": 10,
            "sha256": digest(b"x"),
        }
    )
    assert older["kind"] == "recording" and "frames_choice" not in older


def test_frames_come_back_as_text_chunks_and_rows_with_a_screened_frame_counted(tmp_path: Path) -> None:
    w = world(tmp_path)
    cloud = Cloud()
    source = extract(w, video_source(w), cloud)
    assert source["kind"] == "video" and source["state"] == "partial"  # OCR'd units ask for the learner's review
    assert source["duration_ms"] == 95000 and source["frames"] == 3 and source["screened_frames"] == 1
    assert cloud.extracted[0]["source"]["frames_choice"] == "auto"
    chunks = w.desk.selected([{"source_id": source["source_id"], "revision": 1}], ready=False)
    assert [c["locator"]["kind"] for c in chunks] == ["time", "time", "frame"]
    assert chunks[2]["locator"] == {"kind": "frame", "at_ms": 40000, "frame_id": FRAME_READ}
    assert chunks[2]["text"].startswith("On screen at 0:40:")
    rows = w.conn.execute(
        "SELECT frame_id, at_ms, reason, read_state, text FROM study_frames ORDER BY at_ms"
    ).fetchall()
    assert rows == [
        (FRAME_SCREENED, 0, "scene", "screened", ""),
        (FRAME_READ, 40000, "scene", "read", "On screen at 0:40:\nR = u^2 sin 2theta / g"),
        (FRAME_BLANK, 75000, "chapter", "unreadable", ""),
    ]
    # No image anywhere: the file is the only blob, and the rows hold text or nothing.
    assert w.conn.execute("SELECT count(*) FROM study_revisions WHERE blob_ref IS NOT NULL").fetchone()[0] == 1
    # The player is served the file by its own bytes.
    data, media = w.desk.media(source["source_id"], 1)
    assert data == MP4 and media == "video/mp4"
    # Erasing the source takes its frames with it (DAT-22).
    w.desk.delete(source["source_id"])
    assert w.conn.execute("SELECT count(*) FROM study_frames").fetchone()[0] == 0


def test_a_file_with_no_video_stream_is_downgraded_to_a_recording_in_the_extracted_revision(tmp_path: Path) -> None:
    w = world(tmp_path)
    source = extract(w, video_source(w), Cloud(has_video=False))
    assert source["kind"] == "recording" and source["duration_ms"] == 95000 and source["revision"] == 1
    assert "frames" not in source and "screened_frames" not in source
    assert w.conn.execute("SELECT count(*) FROM study_frames").fetchone()[0] == 0
    chunks = w.desk.selected([{"source_id": source["source_id"], "revision": 1}], ready=False)
    assert [c["locator"]["kind"] for c in chunks] == ["time", "time"]
    assert errors("study/workspace#/$defs/Source", source) == []


def test_a_quiz_item_cites_a_frame_locator(tmp_path: Path) -> None:
    w = world(tmp_path)
    cloud = Cloud()
    source = extract(w, video_source(w), cloud)
    job = w.desk.create_job({"kind": "quiz", "execution": "prefer_cloud", "count": 2, "confirm_readable_only": True,
                             "sources": [{"source_id": source["source_id"], "revision": 1}]})  # fmt: skip
    queue = StudyQueue(lambda: w.conn, lambda: None, lambda: False, w.clock, w.desk.settings)
    queue.cloud = cloud
    asyncio.run(queue.run(w.desk, job["job_id"]))
    done = w.desk.job(job["job_id"])
    assert done["state"] == "completed", done
    aid = w.desk.aid(done["result_ids"][0])
    items = w.desk.quiz(aid["quiz_id"])["view"]["items"]
    chunks = {
        c["chunk_id"]: c for c in w.desk.selected([{"source_id": source["source_id"], "revision": 1}], ready=False)
    }
    cited = chunks[items[0]["stem"]["citations"][0]["chunk_id"]]
    assert cited["locator"]["kind"] == "frame" and cited["locator"]["at_ms"] == 40000  # "0:40 · on screen"
    assert items[0]["stem"]["citations"][0]["quote"] == "R = u^2 sin 2theta / g"
    # The quiz went to the model with the frame's text as a passage: text, never a picture (JM-D34).
    assert cloud.processed and all("png" not in json.dumps(r).lower() for r in cloud.processed)


def test_frames_have_a_retention_rule_a_profile_store_and_a_migration_that_matches_the_contract(tmp_path: Path) -> None:
    rule = next(r for r in RULES if "study_frames" in r.tables)
    assert rule.row_class == "video frames" and rule.database == "learner" and rule.purge is None and rule.removed_by
    assert any(s.rule == "video frames" for s in PROFILE_STORES)
    # A profile migrated through v23 holds the same study_frames table as a database made from the contract.
    conn, _ = open_database(tmp_path / "learner.db", "learner")
    migrated = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'study_frames'").fetchone()[0]
    assert conn.execute("PRAGMA user_version").fetchone()[0] >= 23
    conn.close()
    fresh = sqlite3.connect(":memory:")
    fresh.executescript(LEARNER)
    contract = fresh.execute("SELECT sql FROM sqlite_master WHERE name = 'study_frames'").fetchone()[0]
    assert " ".join(migrated.split()) == " ".join(contract.split())
