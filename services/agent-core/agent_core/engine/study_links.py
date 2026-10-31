"""A YouTube link and a pasted transcript as a Study source (SPEC §20.3, §20.4, W9).

Jana fetches nothing (JM-D30): the learner pastes the transcript YouTube's own panel shows, and these functions turn
it into timed chunks and chapters on the device. Two pastes are read: the panel's **alternating** form (a timestamp
line, then the text line; chapter headings interleaved when the video has them) and the **same-line** form
(`[m:ss] text` or `m:ss text`). Timestamps are `m:ss`, `mm:ss` or `h:mm:ss`. A line with no timestamp between two
timestamped blocks is a chapter heading, kept as a chapter and never as a chunk; a gap over 20 s starts a chapter
too. Lines merge into chunks of at most 4,000 code points, each line keeping its own moment as a `[m:ss]` prefix, so
every line, citation and companion excerpt can name and open its moment. A paste whose last timestamp passes 2:00:00
(the `Locator.time` bound) is refused; a paste with no timestamp at all is one plain text unit (no moments)."""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlsplit

VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
MAX_MS = 7_200_000  # Locator.time's bound: two hours
CHUNK_CODE_POINTS = 4_000
GAP_MS = 20_000
TAIL_MS = 5_000  # the last chunk's end past its last line's start (a locator needs end > start)
HEADING_MAX = 120
_TS = r"(?:(\d{1,2}):)?(\d{1,2}):(\d{2})"
_BARE = re.compile(rf"^\[?{_TS}\]?\s*$")
_SAME_LINE = re.compile(rf"^\[?{_TS}\]?[\s\-\u2013:]+(\S.*)$")  # a dash or an en dash between
_PREFIX = re.compile(r"^\[(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\]\s?")


class TranscriptTooLong(ValueError):
    """The paste's last timestamp passes two hours (`MAX_MS`)."""


def parse_youtube(url: str) -> str | None:
    """The video id of a YouTube watch, youtu.be, shorts or embed link, else None (`unsupported_link`)."""
    raw = url.strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = "https://" + raw
    try:
        parts = urlsplit(raw)
    except ValueError:
        return None
    if parts.scheme not in ("http", "https"):
        return None
    host = parts.netloc.lower().split("@")[-1].split(":")[0]
    for prefix in ("www.", "m.", "music."):
        host = host.removeprefix(prefix)
    path = [p for p in parts.path.split("/") if p]
    candidate: str | None = None
    if host == "youtu.be":
        candidate = path[0] if path else None
    elif host in ("youtube.com", "youtube-nocookie.com"):
        if path[:1] == ["watch"]:
            values = parse_qs(parts.query).get("v")
            candidate = values[0] if values else None
        elif len(path) >= 2 and path[0] in ("shorts", "embed", "live"):
            candidate = path[1]
    return candidate if candidate is not None and VIDEO_ID.fullmatch(candidate) else None


def youtube_url(video_id: str, at_ms: int = 0) -> str:
    """The link a moment opens in the learner's browser (JM-D31): youtube.com/watch?v=<id>&t=<seconds>."""
    seconds = max(0, int(at_ms) // 1000)
    return f"https://www.youtube.com/watch?v={video_id}" + (f"&t={seconds}" if seconds else "")


def moment_label(ms: int) -> str:
    """A moment's label, as the panel writes it: `m:ss` under an hour, `h:mm:ss` from one hour."""
    seconds = max(0, int(ms)) // 1000
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _ms(hours: str | None, minutes: str, seconds: str) -> int:
    return (int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds)) * 1000


def line_moment(line: str) -> int | None:
    """The moment a chunk line carries as its `[m:ss]` prefix, or None."""
    found = _PREFIX.match(line)
    return _ms(*found.groups()) if found else None


def moment_at(text: str, offset: int) -> int | None:
    """The moment of the line of `text` that holds code point `offset` (a citation's start), from its prefix."""
    if offset < 0 or offset > len(text):
        return None
    start = text.rfind("\n", 0, offset) + 1
    end = text.find("\n", start)
    return line_moment(text[start : end if end >= 0 else len(text)])


_ANY_MOMENT = re.compile(r"\[((?:\d{1,2}:)?\d{1,2}:\d{2})\]")


def first_moment(text: str) -> int | None:
    """The first `[m:ss]` moment anywhere in `text` (an excerpt that may start mid-line), or None."""
    found = _ANY_MOMENT.search(text)
    if found is None:
        return None
    parts = found.group(1).split(":")
    hours = parts[0] if len(parts) == 3 else None
    return _ms(hours, parts[-2], parts[-1])


def line_text(line: str) -> str:
    """A chunk line without its moment prefix."""
    return _PREFIX.sub("", line, count=1)


@dataclass
class Transcript:
    kind: str  # "timed" | "plain"
    lines: list[tuple[int, str]] = field(default_factory=list)  # (ms, text) in order
    chapters: list[dict[str, Any]] = field(default_factory=list)  # {start_ms, end_ms, title}
    chunks: list[dict[str, Any]] = field(default_factory=list)  # {start_ms, end_ms, text}
    text: str = ""  # the plain paste, when there are no timestamps
    duration_ms: int = 0


def _entries(text: str) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    """(lines, headings): each line as (ms, text); each heading with the index of the line it precedes."""
    lines: list[tuple[int, str]] = []
    headings: list[tuple[int, str]] = []  # (index into lines of the next line, title)
    pending: int | None = None
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.strip()
        if not line:
            continue
        bare = _BARE.match(line)
        if bare:
            pending = _ms(*bare.groups())
            continue
        same = _SAME_LINE.match(line)
        if same:
            hours, minutes, seconds, words = same.groups()
            lines.append((_ms(hours, minutes, seconds), words.strip()))
            pending = None
            continue
        if pending is not None:
            lines.append((pending, line))
            pending = None
            continue
        # A line with no timestamp of its own: a heading when it reads like one, else a wrapped continuation.
        if len(line) <= HEADING_MAX and line[-1] not in ".?!,;:" and (not lines or len(line.split()) <= 12):
            headings.append((len(lines), line))
        elif lines:
            ms, words = lines[-1]
            lines[-1] = (ms, words + " " + line)
        else:
            headings.append((len(lines), line[:HEADING_MAX]))
    # Keep moments monotone: a line stamped earlier than its predecessor takes the predecessor's moment.
    for i in range(1, len(lines)):
        if lines[i][0] < lines[i - 1][0]:
            lines[i] = (lines[i - 1][0], lines[i][1])
    return lines, headings


def _title_from(words: str) -> str:
    title = " ".join(words.split()[:8])[:60].strip()
    return (title[0].upper() + title[1:]) if title else "Chapter"


def parse_transcript(text: str) -> Transcript:
    """A pasted transcript as timed lines, chapters and chunks (SPEC §20.3), or a plain text when it has no
    timestamps. Raises `TranscriptTooLong` past two hours."""
    lines, headings = _entries(text)
    if not lines:
        return Transcript("plain", text=text.strip())
    # The last line needs a locator that ends inside the bound, so its moment must fall short of 2:00:00.
    if lines[-1][0] >= MAX_MS:
        raise TranscriptTooLong(moment_label(MAX_MS))
    starts: dict[int, str] = {}  # line index -> chapter title
    for index, title in headings:
        if index < len(lines):
            starts.setdefault(index, title)
    for i in range(1, len(lines)):
        if lines[i][0] - lines[i - 1][0] > GAP_MS and i not in starts:
            starts[i] = _title_from(lines[i][1])
    if starts and 0 not in starts:
        starts[0] = _title_from(lines[0][1])
    chunks: list[dict[str, Any]] = []
    current: list[str] = []
    current_start = lines[0][0]
    size = 0
    for i, (ms, words) in enumerate(lines):
        rendered = f"[{moment_label(ms)}] {words}"
        if current and (i in starts or size + 1 + len(rendered) > CHUNK_CODE_POINTS):
            chunks.append({"start_ms": current_start, "end_ms": 0, "text": "\n".join(current)})
            current, size, current_start = [], 0, ms
        current.append(rendered)
        size += len(rendered) + 1
    chunks.append({"start_ms": current_start, "end_ms": 0, "text": "\n".join(current)})
    last_end = min(MAX_MS, lines[-1][0] + TAIL_MS)
    for a, b in itertools.pairwise(chunks):
        a["end_ms"] = max(int(a["start_ms"]) + 1, int(b["start_ms"]))
    chunks[-1]["end_ms"] = max(int(chunks[-1]["start_ms"]) + 1, last_end)
    chapters: list[dict[str, Any]] = []
    for index in sorted(starts):
        chapters.append({"start_ms": lines[index][0], "end_ms": 0, "title": starts[index][:HEADING_MAX]})
    for a, b in itertools.pairwise(chapters):
        a["end_ms"] = max(int(a["start_ms"]) + 1, int(b["start_ms"]))
    if chapters:
        chapters[-1]["end_ms"] = max(int(chapters[-1]["start_ms"]) + 1, int(chunks[-1]["end_ms"]))
    return Transcript("timed", lines=lines, chapters=chapters, chunks=chunks, duration_ms=int(chunks[-1]["end_ms"]))
