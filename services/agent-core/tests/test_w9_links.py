"""SPEC §20.9 `test_w9_links.py` (W9): the YouTube id parser over every accepted link form and the refusals; the
transcript parser over the verbatim panel paste (alternating lines with chapter headings), the same-line form,
headings as chapters, merged lines that keep their moments, a gap that starts a chapter, the two-hour bound and the
no-timestamp paste. The lecture text is synthetic; the paste's form is YouTube's panel's."""

from __future__ import annotations

from pathlib import Path

import pytest
from agent_core.engine.study_links import (
    CHUNK_CODE_POINTS,
    TranscriptTooLong,
    line_moment,
    line_text,
    moment_at,
    moment_label,
    parse_transcript,
    parse_youtube,
    youtube_url,
)

PANEL = (Path(__file__).parent / "fixtures" / "w9" / "youtube_panel_projectile.txt").read_text()
VIDEO = "dQw4w9WgXcQ"


def test_each_accepted_youtube_link_form_yields_the_id_and_any_other_link_is_refused() -> None:
    accepted = [
        f"https://www.youtube.com/watch?v={VIDEO}",
        f"https://youtube.com/watch?v={VIDEO}&t=252s",
        f"https://m.youtube.com/watch?feature=share&v={VIDEO}",
        f"https://youtu.be/{VIDEO}",
        f"https://youtu.be/{VIDEO}?t=252",
        f"https://www.youtube.com/shorts/{VIDEO}",
        f"https://www.youtube.com/embed/{VIDEO}?start=12",
        f"https://www.youtube-nocookie.com/embed/{VIDEO}",
        f"youtube.com/watch?v={VIDEO}",  # no scheme: still the watch page
    ]
    assert [parse_youtube(u) for u in accepted] == [VIDEO] * len(accepted)
    refused = [
        "https://vimeo.com/123456",
        "https://www.youtube.com/",
        "https://www.youtube.com/watch",
        "https://www.youtube.com/watch?v=short",
        "https://www.youtube.com/channel/UCabc",
        "https://example.com/watch?v=" + VIDEO,
        "ftp://youtu.be/" + VIDEO,
        "",
        "not a link at all",
    ]
    assert [parse_youtube(u) for u in refused] == [None] * len(refused)


def test_the_verbatim_panel_paste_parses_to_timed_chunks_and_chapters() -> None:
    parsed = parse_transcript(PANEL)
    assert parsed.kind == "timed"
    # Every timestamp line became a moment; headings are chapters, never lines.
    assert parsed.lines[0] == (0, "in this lecture we look at projectile motion")
    assert (
        252_000,
        "substituting the time of flight gives the range equation R equals u squared sin two theta over g",
    ) in parsed.lines
    assert all("Introduction" != words and "Time of flight" != words for _, words in parsed.lines)
    titles = [c["title"] for c in parsed.chapters]
    assert titles == ["Introduction", "Resolving the velocity", "The range equation", "Time of flight",
                      "Maximum height", "Worked examples"]  # fmt: skip
    starts = [c["start_ms"] for c in parsed.chapters]
    assert starts == [0, 48_000, 230_000, 400_000, 495_000, 580_000]
    # Chapters tile the transcript in order, each ending where the next begins.
    for a, b in zip(parsed.chapters, parsed.chapters[1:], strict=False):
        assert a["end_ms"] == b["start_ms"]
    assert parsed.chapters[-1]["end_ms"] == parsed.duration_ms
    # A chunk starts at every chapter; it carries its lines with their moments as prefixes.
    assert [c["start_ms"] for c in parsed.chunks] == starts
    range_chunk = parsed.chunks[2]
    assert str(range_chunk["text"]).startswith("[3:50] now let's derive how far the ball travels")
    assert "[4:12] substituting the time of flight gives the range equation" in str(range_chunk["text"])
    assert range_chunk["end_ms"] == 400_000
    assert parsed.duration_ms == 620_000 + 5_000  # the last line's moment plus the tail


def test_the_same_line_form_parses_like_the_panel_form() -> None:
    same = "\n".join(
        [
            "0:00 in this lecture we look at projectile motion",
            "[0:04] a projectile is any object thrown into the air",
            "Resolving the velocity",
            "0:48 - start with a ball launched at speed u",
            "1:02 the horizontal component of the velocity is u cos theta",
        ]
    )
    parsed = parse_transcript(same)
    assert parsed.kind == "timed"
    assert [ms for ms, _ in parsed.lines] == [0, 4_000, 48_000, 62_000]
    assert [c["title"] for c in parsed.chapters] == [
        "In this lecture we look at projectile motion",
        "Resolving the velocity",
    ]
    assert [c["start_ms"] for c in parsed.chunks] == [0, 48_000]
    assert str(parsed.chunks[1]["text"]).splitlines() == [
        "[0:48] start with a ball launched at speed u",
        "[1:02] the horizontal component of the velocity is u cos theta",
    ]


def test_merged_lines_stay_under_the_chunk_bound_and_every_line_keeps_its_moment() -> None:
    long = "\n".join(f"{i // 60}:{i % 60:02d}\n{'word ' * 40}line {i}" for i in range(0, 600, 5))
    parsed = parse_transcript(long)
    assert parsed.chapters == []  # no heading, no gap over twenty seconds
    assert len(parsed.chunks) > 1
    assert all(len(str(c["text"])) <= CHUNK_CODE_POINTS for c in parsed.chunks)
    for a, b in zip(parsed.chunks, parsed.chunks[1:], strict=False):
        assert a["end_ms"] == b["start_ms"]
    for chunk in parsed.chunks:
        lines = str(chunk["text"]).splitlines()
        assert line_moment(lines[0]) == chunk["start_ms"]
        assert all(line_moment(line) is not None for line in lines)
    # A citation's start offset names its line's moment.
    text = str(parsed.chunks[0]["text"])
    second = text.index("\n") + 3
    assert moment_at(text, second) == 5_000 and moment_at(text, 0) == 0
    assert line_text("[4:12] the range equation") == "the range equation"


def test_a_gap_of_a_minute_or_more_starts_a_chapter_titled_by_its_first_words() -> None:
    parsed = parse_transcript(
        "0:00\nfirst part of the talk\n0:10\nstill the first part\n1:10\nnow a new idea begins here\n1:15\nand goes on"
    )
    assert [(c["start_ms"], c["title"]) for c in parsed.chapters] == [
        (0, "First part of the talk"),
        (70_000, "Now a new idea begins here"),
    ]
    assert [c["start_ms"] for c in parsed.chunks] == [0, 70_000]
    # A gap short of a minute is not a chapter (the old 20 s rule made one of every line of a sparse paste).
    assert parse_transcript("0:00\nfirst\n0:59\nstill the same chapter").chapters == []


def test_a_sparse_transcript_with_a_line_every_half_minute_is_not_a_chapter_a_line() -> None:
    """Live-run fix 2026-11-01: a panel paste with one line every 30 to 40 s made a chapter of every line."""
    sparse = "\n".join(f"{(i * 35) // 60}:{(i * 35) % 60:02d}\nline {i} of a slow lecture" for i in range(20))
    parsed = parse_transcript(sparse)
    assert parsed.chapters == [] and len(parsed.lines) == 20
    assert len(parsed.chunks) == 1


def test_gap_made_chapters_are_capped_at_twelve_keeping_the_largest_gaps() -> None:
    # Twenty gaps, every one a minute or more, growing by five seconds: only the twelve largest start chapters.
    moments, at = [0], 0
    for i in range(20):
        at += 60 + i * 5
        moments.append(at)
    paste = "\n".join(f"{m // 60}:{m % 60:02d}\nwords at {m}" for m in moments)
    parsed = parse_transcript(paste)
    kept = {c["start_ms"] for c in parsed.chapters}
    assert kept == {0, *(m * 1000 for m in moments[9:])}  # the opening chapter and the twelve widest gaps
    assert len(parsed.chapters) == 13
    # A heading always starts a chapter, over and above the twelve.
    stamp = f"\n{moments[3] // 60}:{moments[3] % 60:02d}\n"
    headed = parse_transcript(paste.replace(stamp, "\nA heading" + stamp))
    assert ("A heading", moments[3] * 1000) in {(c["title"], c["start_ms"]) for c in headed.chapters}
    assert len(headed.chapters) == 14


def test_a_paste_past_two_hours_is_refused_with_the_limit_named() -> None:
    with pytest.raises(TranscriptTooLong) as refused:
        parse_transcript("0:00\nstart\n2:00:01\none second too far")
    assert str(refused.value) == "2:00:00"
    with pytest.raises(TranscriptTooLong):  # a line at 2:00:00 itself has no room for a locator inside the bound
        parse_transcript("0:00\nstart\n2:00:00\nthe last words")
    # Just inside the bound: the last chunk's end is capped at two hours.
    parsed = parse_transcript("0:00\nstart\n1:59:59\nthe last words")
    assert parsed.duration_ms == 7_200_000 and parsed.chunks[-1]["end_ms"] == 7_200_000


def test_a_paste_with_no_timestamps_is_plain_text() -> None:
    parsed = parse_transcript(
        "Projectile motion\n\nA projectile moves under gravity alone.\nThe range depends on sin 2θ."
    )
    assert parsed.kind == "plain" and parsed.lines == [] and parsed.chunks == [] and parsed.chapters == []
    assert parsed.text.startswith("Projectile motion") and parsed.duration_ms == 0


def test_moment_labels_and_the_browser_link() -> None:
    assert moment_label(252_000) == "4:12" and moment_label(3_852_000) == "1:04:12" and moment_label(0) == "0:00"
    assert youtube_url(VIDEO, 252_900) == f"https://www.youtube.com/watch?v={VIDEO}&t=252"
    assert youtube_url(VIDEO) == f"https://www.youtube.com/watch?v={VIDEO}"
