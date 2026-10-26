"""Explain it back: a mastery check whose items all passed confirms mastery only once the learner explains the KC's
key points in their own words. The judge is scripted here (the Checker's judge role in the app); it must quote the
learner's words for a point to count. One targeted follow-up after a miss, never the answer; a second miss is not
yet. Synthetic items and KC, as in the M16 checks."""

from __future__ import annotations

import asyncio
from typing import Any

from agent_core.contracts import errors as contract_errors
from test_m16_assessment import KC, answer, desk  # noqa: F401  (desk is the shared fixture)

POINTS = [
    {"id": "kp_combine", "text": {"en": "Adding combines two amounts into one total."},
     "follow_up": {"en": "What happens to the two amounts when you add them?"}},
    {"id": "kp_order", "text": {"en": "The order of the numbers does not change the total."},
     "follow_up": {"en": "Does 3 + 5 give the same total as 5 + 3? Why?"}},
]  # fmt: skip


def run(coro: Any) -> Any:
    return asyncio.new_event_loop().run_until_complete(coro)


class Judge:
    """Passes a point when the explanation contains its cue words, quoting them; records what it was asked."""

    def __init__(self, cues: dict[str, str], quote: str | None = None, answers: bool = True) -> None:
        self.cues, self.quote, self.answers = cues, quote, answers
        self.asked: list[list[str]] = []

    async def __call__(self, criteria: Any, text: str) -> list[dict[str, Any]] | None:
        self.asked.append([cid for cid, _ in criteria])
        if not self.answers:
            return None
        out = []
        for cid, _ in criteria:
            cue = self.cues.get(cid, "")
            met = bool(cue) and cue in text
            out.append({"id": cid, "pass": met or self.quote is not None,
                        "evidence": self.quote if self.quote is not None else (cue if met else ""),
                        "status": "judged"})  # fmt: skip
        return out


CUES = {"kp_combine": "put the two amounts together", "kp_order": "order does not matter"}


def explaining(d: Any, c: Any, judge: Judge, points: list[dict[str, Any]] | None = POINTS) -> dict[str, Any]:
    d.explain_judge = judge
    d.content.records["kcs"][KC]["key_points"] = points or []
    state = d.start_assessment("mastery_check", "mathematics", KC)
    for n in range(2):
        state = run(d.assessment_answer(state["assessment_id"], str(n), state["current_item"]["item_id"], answer()))
    c.advance(int(d.settings.mastery_check_min_spacing_hours * 3_600_000))
    state = d.assessment(state["assessment_id"])
    return run(d.assessment_answer(state["assessment_id"], "third", state["current_item"]["item_id"], answer()))


def adopted(state: dict[str, Any]) -> dict[str, Any]:
    """The view less `last_mark`, which the reply carries ahead of its adoption (as before this change)."""
    return {k: v for k, v in state.items() if k != "last_mark"}


def status(d: Any) -> str | None:
    row = d.learner.conn.execute("SELECT status FROM kc_mastery WHERE kc_id = ?", (KC,)).fetchone()
    return row[0] if row else None


def checks(d: Any) -> list[str]:
    return [e.payload["check_state"] for e in d.learner.log.by_seq() if e.type == "mastery_check"]


def test_passed_items_wait_for_the_explanation(desk: Any) -> None:
    d, c = desk
    state = explaining(d, c, Judge(CUES))
    assert state["state"] == "explaining" and state["current_item"] is None
    assert state["explain"] == {"statement": "Add", "follow_up": None, "attempts": 0, "outcome": "awaiting"}
    assert contract_errors("learning/student-records#/$defs/AssessmentState", adopted(state)) == []
    assert status(d) != "mastered" and checks(d)[-1] == "in_progress"
    # Opening it again, or starting a check for the subject, comes back to the same explanation.
    assert d.assessment(state["assessment_id"])["state"] == "explaining"
    assert d.start_assessment("mastery_check", "mathematics", KC)["assessment_id"] == state["assessment_id"]


def test_an_explanation_with_every_key_point_confirms_mastery(desk: Any) -> None:
    d, c = desk
    state = explaining(d, c, Judge(CUES))
    said = "You put the two amounts together to get one total, and the order does not matter."
    state = run(d.explain_back(state["assessment_id"], "e1", said, "typed"))
    assert state["state"] == "completed" and state["explain"]["outcome"] == "passed"
    assert status(d) == "mastered" and checks(d)[-1] == "passed"
    assert contract_errors("learning/student-records#/$defs/AssessmentState", adopted(state)) == []


def test_a_miss_gets_one_targeted_follow_up_never_the_point(desk: Any) -> None:
    d, c = desk
    judge = Judge(CUES)
    state = explaining(d, c, judge)
    state = run(d.explain_back(state["assessment_id"], "e1", "You put the two amounts together.", "typed"))
    assert state["state"] == "explaining" and state["explain"]["outcome"] == "follow_up"
    assert state["explain"]["follow_up"] == "Does 3 + 5 give the same total as 5 + 3? Why?"
    assert "does not change the total" not in str(state)  # the key point itself is never shown
    assert status(d) != "mastered"
    # The follow-up is judged on the missed point only; met points stay met.
    state = run(d.explain_back(state["assessment_id"], "e2", "Yes, the order does not matter for adding.", "spoken"))
    assert judge.asked == [["kp_combine", "kp_order"], ["kp_order"]]
    assert state["state"] == "completed" and status(d) == "mastered"


def test_the_follow_up_missed_is_not_yet(desk: Any) -> None:
    d, c = desk
    state = explaining(d, c, Judge(CUES))
    state = run(d.explain_back(state["assessment_id"], "e1", "You put the two amounts together.", "typed"))
    state = run(d.explain_back(state["assessment_id"], "e2", "It just gets bigger.", "typed"))
    assert state["state"] == "failed" and state["explain"]["outcome"] == "not_yet"
    assert state["retry_at"] is not None and state["explain"]["follow_up"] is None
    assert status(d) != "mastered" and checks(d)[-1] == "failed"


def test_a_pass_must_quote_the_learners_own_words(desk: Any) -> None:
    d, c = desk
    state = explaining(d, c, Judge(CUES, quote="adding combines amounts into a total"))
    state = run(d.explain_back(state["assessment_id"], "e1", "Adding is easy.", "typed"))
    assert state["explain"]["outcome"] == "follow_up" and status(d) != "mastered"


def test_no_judge_answering_never_counts(desk: Any) -> None:
    d, c = desk
    state = explaining(d, c, Judge(CUES, answers=False))
    said = "You put the two amounts together and the order does not matter."
    state = run(d.explain_back(state["assessment_id"], "e1", said, "typed"))
    assert state["state"] == "explaining" and state["explain"]["outcome"] == "unavailable"
    assert state["explain"]["attempts"] == 0 and status(d) != "mastered"


def test_a_kc_without_key_points_is_mastered_by_its_items(desk: Any) -> None:
    d, c = desk
    state = explaining(d, c, Judge(CUES), points=None)
    assert state["state"] == "completed" and "explain" not in state and status(d) == "mastered"


def test_the_same_request_is_answered_once(desk: Any) -> None:
    d, c = desk
    judge = Judge(CUES)
    state = explaining(d, c, judge)
    first = run(d.explain_back(state["assessment_id"], "e1", "You put the two amounts together.", "typed"))
    again = run(d.explain_back(state["assessment_id"], "e1", "You put the two amounts together.", "typed"))
    assert first == again and len(judge.asked) == 1
