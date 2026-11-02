"""Adversarial regression cases: sharing a nearby word is not evidence for a personalized claim."""

from agent_core.engine.companion import fact_binding_errors


def test_a_long_skill_statement_is_clipped_at_a_word_never_mid_word() -> None:
    from agent_core.engine.companion_facts import STATEMENT_MAX, clip, from_progress

    long = (
        "Explain why the horizontal velocity of a projectile stays constant while gravity changes its vertical velocity"
    )
    assert len(long) > STATEMENT_MAX
    clipped = clip(long)
    assert len(clipped) <= STATEMENT_MAX and clipped.endswith("…") and not clipped.endswith("vertica…")
    assert clipped == "Explain why the horizontal velocity of a projectile stays constant while gravity changes its…"
    assert clip("short") == "short"
    assert clip("x" * 150) == "x" * 99 + "…"  # no space to cut at: a hard cut
    facts = from_progress({"bands": [{"ref": "r1", "skill": long, "band": "learning"}]}, period="2026-11-02")
    assert facts[0].statement == f"Your practice on {clipped}: learning."


def test_neighbouring_card_word_cannot_bind_an_exam_count() -> None:
    assert fact_binding_errors("Your exam is in 12 days; cards are due.", ["cards due 12; exam in 19 days"])


def test_spelled_out_progress_counts_need_evidence() -> None:
    assert fact_binding_errors("You answered twelve questions correctly.", [])


def test_mastery_claim_requires_a_typed_source() -> None:
    assert fact_binding_errors("You have mastered motion.", [])


def test_negative_schedule_claims_cannot_bypass_typed_facts() -> None:
    from agent_core.engine.companion_facts import model_claim_errors

    assert model_claim_errors("No plan is set for today and you have no cards due right now.")
    assert model_claim_errors("You have no reviews due.")
    assert model_claim_errors("There aren't any cards due today.")
    assert not model_claim_errors("Would you like to make a plan or review cards?")


def test_selected_fact_preserves_metric_period_and_source() -> None:
    import pytest
    from agent_core.engine.companion_facts import from_progress, selected_text

    facts = from_progress({"due": {"learner_cards": 12}, "exam_distance_days": 19}, period="2026-10-30")
    shown = selected_text(facts, [1])
    assert "cards due: 12" in shown and "review schedule" in shown and "2026-10-30" in shown
    assert "19" not in shown and "exam" not in shown
    with pytest.raises(ValueError, match="not supplied"):
        selected_text(facts, [3])


def test_progress_fact_is_code_rendered_in_the_actual_reply(tmp_path) -> None:
    import json

    from engine_harness import reply
    from w8_companion_harness import run, stop_core, thread

    async def go() -> None:
        t = await thread(
            tmp_path,
            {
                "companion": [
                    reply(
                        json.dumps(
                            {
                                "text": "Would you like to review now?",
                                "action": None,
                                "fact_refs": [1],
                            }
                        )
                    )
                ]
            },
        )
        try:
            opened = await t.open()
            await t.say(opened["session_id"], "What should I review?")
            snap = await t.snapshot(opened["session_id"])
            text = " ".join(p.get("text", "") for p in snap["parts"].values())
            assert "cards due: 0" in text and "Source: review schedule" in text
        finally:
            await stop_core(t.r)

    run(go())


def test_review_failure_is_not_presented_as_secure() -> None:
    from agent_core.memory.render import BANDS

    assert BANDS["needs_review"] != "secure"


def test_opener_cannot_swap_subjects_or_add_a_mastery_claim() -> None:
    from agent_core.engine.companion import opener_errors
    from agent_core.engine.companion_opener import Facts

    found = Facts("2026-10-30", "study", "physics", 0, None, False, "2026-10-30")
    assert opener_errors("You worked on biology today.", found, ["last_session"])
    assert opener_errors("You mastered physics today.", found, ["last_session"])
