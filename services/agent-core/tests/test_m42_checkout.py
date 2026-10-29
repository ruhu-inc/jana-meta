"""A signed scope-specific checkout grant, never an unsigned guardian checkbox or cloud-tier inference."""

from agent_core.config import Settings
from agent_core.store import consents, subscription
from test_m10a_profiles import student
from test_m10e_consent import with_api


def test_pending_profile_does_not_disable_an_already_approved_profile():
    stored = {
        "profiles": ["approved_adult", "pending_learner"],
        "consent_needed": ["pending_learner"],
        "period_end": 2000,
        "ended_at": None,
    }
    assert subscription.state(stored, 1000) == "pending_consent"
    assert subscription.covers(stored, "approved_adult", 1000)
    assert not subscription.covers(stored, "pending_learner", 1000)
    assert not subscription.covers(stored, "uncovered_profile", 1000)
    assert not subscription.covers(stored, "approved_adult", 2000)
    assert not subscription.covers({**stored, "ended_at": 500}, "approved_adult", 1000)


def test_adult_study_agreement_records_scope_and_first_use(tmp_path):
    async def scenario(api, runtime):
        runtime.core.online = runtime.runtime.attach_online()
        adult = await api.add(student("Synthetic adult", age_band="18_plus"))
        token = (await api.unlock(adult)).json()["profile_token"]
        runtime.core.notices["study_materials"] = ["2026-10.m42-draft"]
        assert runtime.runtime.online.notice_answer(adult, "study_materials") is None
        response = await api.call(
            "PUT",
            f"/v1/profiles/{adult}/consents/study_materials",
            {"action": "on", "notice_version": "2026-10.m42-draft"},
            profile=token,
        )
        assert response.status_code == 200, response.text
        assert runtime.runtime.online.notice_answer(adult, "study_materials") == "accepted"
        with runtime.runtime.directory.open_learner(adult) as conn:
            assert consents.active(conn, "study_materials")[1] == "student_18_plus"

    with_api(tmp_path, scenario, Settings(study_workspace_enabled=True, consent_dpia_ref="synthetic-dpia"))
