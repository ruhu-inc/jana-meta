"""VOC-08: a hyphen joining words is part of the word, never a minus sign. Only a minus in maths (before or between
numbers, variables or expressions) is read "negative" or "minus". Readings are authored independently of the parser."""

import pytest
from agent_core.engine.verbaliser import verbalise

WORD_HYPHENS = [
    ("It is a well-known result.", "It is a well-known result."),
    ("The star is 4.2 light-years away.", "The star is four point two light-years away."),
    ("Draw the x-axis first.", "Draw the x-axis first."),
    ("Check your mother-in-law's sum.", "Check your mother-in-law's sum."),
    ("Take a 20-minute break.", "Take a twenty-minute break."),
    (r"$\text{well-known}$", "well-known"),
]

MINUS_SIGNS = [
    ("5-3", "five minus three"),
    ("x-y", "x minus y"),
    ("2x-y", "two x minus y"),
    ("Try -3 next.", "Try negative three next."),
    ("a - b", "a minus b"),
    (r"$ab-cd$", "a b minus c d"),
    (r"$v^2 - u^2$", "v squared minus u squared"),
    ("x = 10-cos x", "x equals ten minus cos x"),
]


@pytest.mark.parametrize(("written", "spoken"), WORD_HYPHENS)
def test_a_word_hyphen_is_never_read_as_a_sign(written, spoken):
    rendered = verbalise(written)
    assert rendered.text == spoken
    assert "negative" not in rendered.text and "minus" not in rendered.text


@pytest.mark.parametrize(("written", "spoken"), MINUS_SIGNS)
def test_a_minus_in_maths_is_still_read(written, spoken):
    assert verbalise(written).text == spoken
