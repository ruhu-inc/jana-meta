"""SPEC §20.9 `test_w9_video_link_source.py` (W9): the `SourceCreate` video_link variant through `StudyDesk.create`:
ready at once with its timed chunks and chapters, the link kept, `source_added` recorded, personal data redacted from
the paste, the refusals (an unsupported link, a paste past two hours), a paste with no timestamps saved as plain
text, and a corrected transcript parsed again. Every learner, link and line here is synthetic."""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import pytest
from agent_core.contracts import errors
from agent_core.engine.study import StudyError
from agent_core.engine.study_links import line_moment
from test_w8_study_activity import world

PANEL = (Path(__file__).parent / "fixtures" / "w9" / "youtube_panel_projectile.txt").read_text()
VIDEO = "dQw4w9WgXcQ"
URL = f"https://www.youtube.com/watch?v={VIDEO}"


def test_a_video_link_source_is_ready_at_once_with_timed_chunks_chapters_and_the_link(tmp_path: Path) -> None:
    w = world(tmp_path)
    w.visits.open()
    source = w.desk.create({"kind": "video_link", "url": URL, "transcript": PANEL, "title": "Projectile motion"})
    assert errors("study/workspace#/$defs/Source", source) == []
    assert source["kind"] == "video_link" and source["state"] == "ready" and source["title"] == "Projectile motion"
    assert source["link"] == {"provider": "youtube", "video_id": VIDEO, "url": URL}
    assert source["transcript_kind"] == "timed" and source["duration_ms"] == 625_000
    assert [c["title"] for c in source["chapters"]] == ["Introduction", "Resolving the velocity", "The range equation",
                                                         "Time of flight", "Maximum height",
                                                         "Worked examples"]  # fmt: skip
    chunks = w.desk.selected([{"source_id": source["source_id"], "revision": 1}])
    assert [c["locator"]["kind"] for c in chunks] == ["time"] * 6
    assert [c["locator"]["start_ms"] for c in chunks] == [c["start_ms"] for c in source["chapters"]]
    for a, b in itertools.pairwise(chunks):
        assert a["locator"]["end_ms"] == b["locator"]["start_ms"]
    # Every line keeps its moment, so a citation into the chunk names its line's time.
    assert all(line_moment(line) is not None for c in chunks for line in c["text"].splitlines())
    assert "[4:12] substituting the time of flight gives the range equation" in chunks[2]["text"]
    # No extraction job, no upload: the source needs nothing from the gateway (JM-D30).
    assert w.conn.execute("SELECT count(*) FROM study_jobs").fetchone()[0] == 0
    assert (
        w.conn.execute("SELECT blob_ref FROM study_revisions WHERE source_id=?", (source["source_id"],)).fetchone()[0]
        is None
    )
    # The library lists it as any other source; a title is prefilled when none was given.
    untitled = w.desk.create({"kind": "video_link", "url": f"https://youtu.be/{VIDEO}", "transcript": "0:00\nhello"})
    assert untitled["title"] == f"YouTube video {VIDEO}"
    assert {s["source_id"] for s in w.desk.sources()["items"]} >= {source["source_id"], untitled["source_id"]}


def test_adding_a_source_records_one_source_added_activity_with_a_source_ref(tmp_path: Path) -> None:
    w = world(tmp_path)  # the world's text source was added with no Study session open: nothing recorded for it
    assert not w.activity()
    w.visits.open()  # the Study screen is open (its `enter`), as it is when a learner adds a source there
    source = w.desk.create({"kind": "video_link", "url": URL, "transcript": PANEL, "title": "Projectile motion"})
    added = [a for a in w.activity() if a["activity"] == "source_added"]
    assert [a["ref"] for a in added] == [f"src:{source['source_id']}"]
    assert added[0]["_session"] == w.visits.session_id.removeprefix("ses_")  # type: ignore[union-attr]
    assert added[0]["aid_kind"] is None and added[0]["count"] is None and added[0]["outcome"] is None
    for event in w.conn.execute("SELECT payload FROM events WHERE type = 'study_activity'"):
        assert "Projectile" not in event[0] and VIDEO not in event[0]


def test_personal_data_in_the_paste_is_redacted_before_the_chunks_are_frozen(tmp_path: Path) -> None:
    w = world(tmp_path)
    paste = (
        "0:00\nwelcome back everyone\n0:05\nemail me at ada.lovelace@example.com if you have questions\n"
        "0:12\nnow the range equation"
    )
    source = w.desk.create({"kind": "video_link", "url": URL, "transcript": paste})
    text = "\n".join(c["text"] for c in w.desk.selected([{"source_id": source["source_id"], "revision": 1}]))
    assert "ada.lovelace@example.com" not in text and "[0:12] now the range equation" in text


def test_an_unsupported_link_and_a_paste_past_two_hours_are_refused_with_their_reasons(tmp_path: Path) -> None:
    w = world(tmp_path)
    with pytest.raises(StudyError) as refused:
        w.desk.create({"kind": "video_link", "url": "https://vimeo.com/12345", "transcript": PANEL})
    assert refused.value.reason == "unsupported_link"
    with pytest.raises(StudyError) as refused:
        w.desk.create({"kind": "video_link", "url": URL, "transcript": "0:00\nstart\n2:00:01\ntoo far"})
    assert refused.value.reason == "transcript_too_long"
    # The body itself is checked against the contract: a transcript over the limit or an empty one never gets here.
    with pytest.raises(StudyError) as refused:
        w.desk.create({"kind": "video_link", "url": URL, "transcript": ""})
    assert refused.value.reason == "invalid_study_request"
    assert w.conn.execute("SELECT count(*) FROM study_sources").fetchone()[0] == 1  # the world's text source only


def test_a_paste_with_no_timestamps_is_saved_as_plain_text_with_the_link(tmp_path: Path) -> None:
    w = world(tmp_path)
    source = w.desk.create(
        {
            "kind": "video_link",
            "url": URL,
            "transcript": "A lecture on projectile motion.\n\nThe range depends on sin 2θ.",
        }
    )
    assert source["transcript_kind"] == "plain" and "chapters" not in source and "duration_ms" not in source
    assert source["link"]["video_id"] == VIDEO
    chunks = w.desk.selected([{"source_id": source["source_id"], "revision": 1}])
    assert [c["locator"] for c in chunks] == [{"kind": "text", "paragraph": 1}]


def test_a_corrected_transcript_is_parsed_again_and_keeps_its_moments(tmp_path: Path) -> None:
    w = world(tmp_path)
    source = w.desk.create({"kind": "video_link", "url": URL, "transcript": PANEL})
    revised = w.desk.revise(
        source["source_id"], {"expected_revision": 1, "text": "0:00\nfirst line\nNew chapter\n0:30\nsecond line"}
    )
    assert revised["revision"] == 2 and revised["transcript_kind"] == "timed"
    assert [c["title"] for c in revised["chapters"]] == ["First line", "New chapter"]
    chunks = w.desk.selected([{"source_id": source["source_id"], "revision": 2}])
    assert [c["locator"]["start_ms"] for c in chunks] == [0, 30_000]
    stored = json.loads(
        w.conn.execute("SELECT body FROM study_sources WHERE source_id=?", (source["source_id"],)).fetchone()[0]
    )
    assert errors("study/workspace#/$defs/Source", stored) == []
