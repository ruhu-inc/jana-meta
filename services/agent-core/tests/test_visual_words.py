"""The words follow the visual (VSL-16): what the tutor shows and says never speaks of a drawing that is not on
screen. From a browser run: the Coach said "I have drawn its velocity-time graph below, what does the starting point
A tell us?" while the engine fell back to "I can't draw this one, so here it is in words"."""

import asyncio
import json

from agent_core.engine.gates import NUDGES
from agent_core.engine.visual_claims import refers_to_visual, remove_visual_claims
from engine_harness import STATEMENT, checker_steps, close, make_engine, solver_steps, tutor

LOOP = asyncio.new_event_loop()
# The run's reply, said of this harness's problem (a ball thrown up), whose given numbers are not the graph's.
SAID = ("We want how high the ball rises before it stops. I have drawn its velocity-time graph below, what does the "
        "starting point A tell us?")  # fmt: skip
WORDS = "We want how high the ball rises before it stops. How fast is the ball moving at the very top?"
# The run's graph: its numbers are neither given nor cited, so it fails, is corrected once and fails again (VSL-17).
GRAPH = {
    "spec_version": 1,
    "type": "motion_graph",
    "params": {"graph": "velocity_time", "points": [{"id": "A", "t": "0", "value": "0"},
                                                    {"id": "B", "t": "5", "value": "20"}],
               "gradient": [{"id": "slope", "from": "A", "to": "B"}], "units": {"t": "s", "value": "m/s"}},
    "steps": [],
}  # fmt: skip


def run(coro):
    return LOOP.run_until_complete(coro)


def test_a_claim_of_a_drawing_is_found_and_taken_out():
    assert refers_to_visual(SAID) and refers_to_visual("Look at point A.", ["A", "B"])
    assert not refers_to_visual(WORDS, ["A", "B"]) and not refers_to_visual("Point your answer at the speed.")
    kept, removed = remove_visual_claims(SAID, ["A", "B"])
    assert removed and kept == "We want how high the ball rises before it stops."
    # A decimal stays whole: only sentence ends split the text.
    kept, removed = remove_visual_claims("It reaches 2.5 m/s at point B. What is its speed at the start?", ["B"])
    assert removed and kept == "What is its speed at the start?"
    assert remove_visual_claims(WORDS, ["A"]) == (WORDS, False)


def _claims() -> list[dict]:
    """The run's reply, worded a little differently each time (a reply repeated word for word is a text loop)."""
    return [tutor(SAID.replace("We want", start), visual=[GRAPH]) for start in ("We want", "We need", "Now we want")]


def _turn(tmp_path, coach_replies, voice=False):
    """The opening turn, then a student turn whose Coach replies are `coach_replies`."""
    script = {"solver": solver_steps(), "checker": checker_steps(),
              "coach": [tutor("Which quantities does the question give you?"), *coach_replies]}  # fmt: skip

    async def scenario():
        engine, provider = await make_engine(tmp_path, script)
        engine.voice_mode = voice
        await engine.start_problem(STATEMENT)
        opening = len(engine.events.frames)
        result = await engine.student_turn("Can you show me on a graph?")
        await close(engine)
        return provider, [f["event"] for f in engine.events.frames[opening:]], result

    provider, frames, result = run(scenario())
    shown = " ".join(e.get("delta") or e.get("text") or "" for e in frames if e["type"].startswith("text"))
    return [r for r in provider.requests if r.get("_role") == "coach"], frames, shown, result


def test_the_coach_is_asked_once_for_words_when_its_visual_is_not_shown(tmp_path):
    coach, frames, shown, result = _turn(tmp_path, [*_claims()[:2], tutor(WORDS, visual=[GRAPH])])
    assert not refers_to_visual(shown, ["A", "B"])
    assert len(coach) == 4 and NUDGES["visual_words"] in json.dumps(coach[3]["messages"][-1])
    assert "I can't draw this one" in json.dumps(frames)  # the visual still fails: words only, and they say so
    assert WORDS in shown and not refers_to_visual(shown, ["A", "B"]) and result.status == "complete"


def test_a_claim_made_again_is_taken_out_and_the_rung_hint_asks(tmp_path):
    coach, frames, shown, _ = _turn(tmp_path, _claims())
    assert len(coach) == 4  # the visual's one correction, then one words-only attempt, never a second
    assert not refers_to_visual(shown, ["A", "B"])
    assert "Now we want how high the ball rises before it stops." in shown and "?" in shown
    assert "I can't draw this one" in json.dumps(frames)


def test_spoken_words_never_point_at_a_drawing_that_is_not_there(tmp_path):
    spoken = [tutor(SAID.replace("We want", start), say_spoken=SAID.replace("We want", start), visual=[GRAPH])
              for start in ("We want", "We need", "Now we want")]  # fmt: skip
    _, _, shown, result = _turn(tmp_path, spoken, voice=True)
    said = result.tutor_turn["say_spoken"]
    assert not refers_to_visual(said, ["A", "B"]) and not refers_to_visual(shown, ["A", "B"])
    assert said.startswith("Now we want how high the ball rises before it stops.") and said.endswith("?")
