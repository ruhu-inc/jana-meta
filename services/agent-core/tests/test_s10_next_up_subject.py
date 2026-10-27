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


def test_a_new_profile_starts_with_its_first_subject_not_the_weakest_prior() -> None:
    """A new profile (Mathematics, then Physics; nothing started): priors are not evidence, so Next up follows the
    profile's own order and offers a Mathematics idea, never a Physics lesson because Physics' priors look lower."""
    s = Settings()
    kcs = [kc("kc.mth.o.algebra.linear", "mathematics", "not_started", 0.5),
           kc("kc.mth.o.number.fractions", "mathematics", "not_started", 0.6),
           kc("kc.phy.o.waves.oscilloscope", "physics", "not_started", 0.1),
           kc("kc.phy.o.forces.weight", "physics", "not_started", 0.2)]  # fmt: skip
    state = PlannerState((SubjectInfo("mathematics", None), SubjectInfo("physics", None)),
                         {k.kc_id: k for k in kcs}, ())  # fmt: skip
    proposal = planner.plan(state, s)
    assert proposal.subjects[0] == "mathematics"
    main = next(b for b in proposal.blocks if b.kind == "main")
    assert all(k.startswith("kc.mth.") for k in main.kc_ids), main
    order = [k.split(".")[1] for b in proposal.alternatives for k in b.kc_ids]
    assert order == sorted(order, key=lambda c: c != "mth"), proposal.alternatives


def test_an_exam_date_still_comes_first() -> None:
    """A nearer exam in the unstarted subject still leads the order (LRN-28)."""
    s = Settings()
    state = placed_in_maths()
    state = PlannerState((SubjectInfo("mathematics", None), SubjectInfo("physics", 200)), state.kcs, ())
    assert planner.plan(state, s).subjects[0] == "physics"
