"""One stray mark must not make a good scanned page unreadable, and an uncertain line still never becomes evidence."""

from __future__ import annotations

from agent_core.tools.study_document import confident_text


def line(text: str, confidence: float = 0.95, spans: int = 0) -> dict[str, object]:
    return {"text": text, "confidence": confidence, "low_confidence_spans": [[0, 1]] * spans}


def test_a_page_with_one_stray_mark_keeps_its_good_lines() -> None:
    lines = [line(f"good line {i}") for i in range(30)] + [line("[?] [?]", 0.32, 2)]
    text = confident_text(lines)
    assert "good line 0" in text and "good line 29" in text
    assert "[?]" not in text


def test_a_low_confidence_line_never_becomes_evidence() -> None:
    assert confident_text([line("clear"), line("clear too"), line("smudged", 0.6)]) == "clear\nclear too"


def test_a_confident_line_with_an_unsure_word_is_left_out() -> None:
    assert confident_text([line("clear"), line("has [?] inside", 0.95, 1)]) == "clear"


def test_a_page_where_most_lines_are_uncertain_counts_as_unreadable() -> None:
    assert confident_text([line("a fragment"), line("x", 0.4), line("y", 0.4), line("z", 0.4)]) == ""


def test_a_page_with_no_lines_is_unreadable() -> None:
    assert confident_text([]) == ""
