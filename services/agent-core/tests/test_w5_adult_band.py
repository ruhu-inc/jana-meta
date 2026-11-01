"""W5 (SPEC §8.2, §17): Jana is for learners aged 18 or over. The engine and the API refuse any other age band, so a
profile that is not `18_plus` is never created, never changed to another band and never opened, whatever the sign-up
form did. Synthetic profiles; no real student data."""

import sqlite3
from pathlib import Path

import pytest
from agent_core.store.profiles import ADULT_BAND, ProfileError, internal_id
from test_m10a_profiles import Api, code, student, with_api

MINOR_BANDS = ("under_13", "13_15", "16_17")


def test_student_helper_makes_adults():
    assert student("Ama")["age_band"] == ADULT_BAND


@pytest.mark.parametrize("band", MINOR_BANDS)
def test_api_refuses_to_create_a_profile_under_18(tmp_path: Path, band: str):
    async def scenario(api: Api, r):
        refused = await api.call("POST", "/v1/profiles", student("Ama", age_band=band))
        assert refused.status_code == 422 and code(refused) == "validation_failed"
        assert (await api.call("GET", "/v1/profiles")).json()["profiles"] == []
        with pytest.raises(ProfileError) as raised:  # the engine refuses too, not only the route
            r.core.directory.create(student("Kofi", age_band=band))
        assert raised.value.code == "validation_failed"
        assert (await api.call("GET", "/v1/profiles")).json()["profiles"] == []

    with_api(tmp_path, scenario)


@pytest.mark.parametrize("extra", [{"age": 34}, {"age": 17}, {"age": "34"}, {"date_of_birth": "1990-05-14"}])
def test_api_takes_no_age_or_birth_date_only_the_band(tmp_path: Path, extra: dict[str, object]):
    """Sign-up checks the age typed into the form on the device; the create request carries only `age_band`, so an
    age (or a date of birth) sent with it is refused and nothing is created."""

    async def scenario(api: Api, r):
        refused = await api.call("POST", "/v1/profiles", {**student("Ama"), **extra})
        assert refused.status_code == 422 and code(refused) == "validation_failed"
        assert (await api.call("GET", "/v1/profiles")).json()["profiles"] == []

    with_api(tmp_path, scenario)


def test_api_creates_and_opens_an_adult_profile(tmp_path: Path):
    async def scenario(api: Api, r):
        adult = await api.add(student("Esi"))
        token = await api.token(adult)
        own = await api.call("GET", f"/v1/profiles/{adult}", profile=token)
        assert own.json()["age_band"] == ADULT_BAND

    with_api(tmp_path, scenario)


@pytest.mark.parametrize("band", MINOR_BANDS)
def test_api_refuses_to_change_a_profile_to_a_band_under_18(tmp_path: Path, band: str):
    async def scenario(api: Api, r):
        adult = await api.add(student("Esi"))
        token = await api.token(adult)
        refused = await api.call("PATCH", f"/v1/profiles/{adult}", {"age_band": band}, profile=token)
        assert refused.status_code == 422 and code(refused) == "validation_failed"
        assert (await api.call("GET", f"/v1/profiles/{adult}", profile=token)).json()["age_band"] == ADULT_BAND
        with pytest.raises(ProfileError):
            r.core.directory.update(adult, {"age_band": band})
        assert r.core.directory.age_band(adult) == ADULT_BAND

    with_api(tmp_path, scenario)


@pytest.mark.parametrize("band", MINOR_BANDS)
def test_a_profile_an_older_build_made_under_18_does_not_open(tmp_path: Path, band: str):
    """An older build created minor profiles; the engine will not run one. Its data stays on the device until the
    learner deletes it."""

    async def scenario(api: Api, r):
        older = await api.add(student("Ama"))
        path = r.core.directory.learner_path(older)
        conn = sqlite3.connect(path)
        with conn:
            conn.execute("UPDATE profile SET age_band = ? WHERE profile_id = ?", (band, internal_id(older)))
        conn.close()
        refused = await api.unlock(older)
        assert refused.status_code == 422 and code(refused) == "validation_failed"
        with pytest.raises(ProfileError):
            r.core.directory.unlock(older)
        assert path.exists()

    with_api(tmp_path, scenario)


@pytest.mark.parametrize("band", MINOR_BANDS)
def test_an_archive_of_a_profile_under_18_is_not_imported(tmp_path: Path, band: str):
    """A profile archive an older build exported for a minor is refused whole: no profile is made from it."""
    import io
    import json
    import zipfile

    from agent_core.store.exports import FORMAT, seal_with_passphrase

    passphrase = "a synthetic passphrase for this test"  # noqa: S105
    out = io.BytesIO()
    profile = {"display_name": "Imported", "avatar": "disc-teal", "level": "O", "subjects": ["physics"],
               "age_band": band, "exam_date": None}  # fmt: skip
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps({"format": FORMAT, "version": 1, "profile": profile}))
        archive.writestr("events.jsonl", "")
        for name in ("settings.json", "consents.json", "notes.json", "study_notes.json"):
            archive.writestr(name, "[]")
    path = tmp_path / "older.janaprofile"
    path.write_bytes(seal_with_passphrase(out.getvalue(), passphrase, 8192, 1))

    async def scenario(api: Api, r):
        reply = await api.call("POST", "/v1/profiles/import",
                               {"source": {"kind": "file", "path": str(path)}, "passphrase": passphrase})  # fmt: skip
        assert reply.status_code == 422 and code(reply) == "validation_failed", reply.text
        assert (await api.call("GET", "/v1/profiles")).json()["profiles"] == []

    with_api(tmp_path / "data", scenario)
