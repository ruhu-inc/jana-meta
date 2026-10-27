"""SPEC §10.2: after a Mathematics placement, "Next up" recommends Mathematics, not a subject the learner has not
started (whose prior mastery made it look weakest). Learners are synthetic."""

from __future__ import annotations

from agent_core.config import Settings
from agent_core.learner import planner
from agent_core.learner.planner import KcPlanInfo, PlannerState, SubjectInfo


def kc(kc_id: str, subject: str, state: str, p: float) -> KcPlanInfo:
    return KcPlanInfo(kc_id, subject, state, p, 1.0)


def placed_in_maths() -> PlannerState:
    """Placed in Mathematics (some ideas learning, one secure); Physics never started, its priors low."""
    kcs = [kc("kc.mth.o.algebra.linear", "mathematics", "learning", 0.55),
           kc("kc.mth.o.algebra.factorise", "mathematics", "learning", 0.45),
           kc("kc.mth.o.number.fractions", "mathematics", "mastered", 0.95),
           kc("kc.phy.o.motion.average_speed", "physics", "not_started", 0.2),
           kc("kc.phy.o.forces.weight", "physics", "not_started", 0.2)]  # fmt: skip
    return PlannerState((SubjectInfo("mathematics", None), SubjectInfo("physics", None)),
                        {k.kc_id: k for k in kcs}, ())  # fmt: skip


def test_next_up_follows_the_placed_subject() -> None:
    s = Settings()
    proposal = planner.plan(placed_in_maths(), s)
    assert proposal.subjects[0] == "mathematics"
    main = next(b for b in proposal.blocks if b.kind == "main")
    assert all(k.startswith("kc.mth.") for k in main.kc_ids), main
    # The other started Mathematics ideas come before any Physics one among the alternatives.
    order = [k.split(".")[1] for b in proposal.alternatives for k in b.kc_ids]
    assert order[0] == "mth" and order == sorted(order, key=lambda c: c != "mth"), proposal.alternatives


def test_an_unstarted_subject_is_still_offered_when_nothing_is_placed() -> None:
    """With no evidence anywhere the usual ranking stands: the weakest subject by its priors first."""
    s = Settings()
    state = PlannerState((SubjectInfo("mathematics", None), SubjectInfo("physics", None)),
                         {"kc.mth.o.a.b": kc("kc.mth.o.a.b", "mathematics", "not_started", 0.5),
                          "kc.phy.o.a.b": kc("kc.phy.o.a.b", "physics", "not_started", 0.2)}, ())  # fmt: skip
    assert planner.plan(state, s).subjects[0] == "physics"


def test_an_exam_date_still_comes_first() -> None:
    """A nearer exam in the unstarted subject still leads the order (LRN-28)."""
    s = Settings()
    state = placed_in_maths()
    state = PlannerState((SubjectInfo("mathematics", None), SubjectInfo("physics", 200)), state.kcs, ())
    assert planner.plan(state, s).subjects[0] == "physics"
