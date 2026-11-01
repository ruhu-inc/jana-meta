"""Network-free checks of the full-app host; no provider key or paid inference."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import httpx
import pytest
from agent_core.api.core import CoreService
from agent_core.config import Settings
from agent_core.engine.assembly import _pin
from agent_core.store import subscription
from agent_core.store.keystore import FileKeyStore
from cloud_gateway.store import GatewayStore
from jana_tools import REPO_ROOT
from jana_tools import hackathon_app as host


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/v1/ping",
        "https://example.com/v1/ping",
        "https://localhost:444/v1/ping",
        "https://user:password@localhost/v1/ping",
        "https://localhost/private",
    ],
)
def test_transport_refuses_other_destinations(url: str) -> None:
    async def run() -> None:
        seen = []

        async def reply(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(204)

        async with httpx.AsyncClient(transport=host.GatewayHop(8081, httpx.MockTransport(reply))) as client:
            with pytest.raises(httpx.ConnectError):
                await client.get(url)
        assert not seen

    asyncio.run(run())


def test_transport_streaming_auth_and_compatibility() -> None:
    async def run() -> None:
        seen = []

        async def reply(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            assert request.url == "http://127.0.0.1:8081/v1/chat/completions"
            assert request.headers["authorization"] == "Bearer synthetic-device-token"
            body = json.loads(await request.aread())
            # Forwarded unchanged: the gateway validates the device contract (which refuses a caller's `store`) and
            # its Meta adapter applies the provider's rules.
            assert body["tool_choice"] == "required" and "store" not in body
            assert int(request.headers["content-length"]) == len(request.content)
            return httpx.Response(200, content=b'data: {"choices":[]}\n\ndata: [DONE]\n\n')

        body = {
            "messages": [],
            "tools": [{"type": "function", "function": {"name": "math_solve", "parameters": {"type": "object"}}}],
            "tool_choice": "required",
            "response_format": {"type": "json_schema", "json_schema": {"schema": {"type": "object"}}},
        }
        async with httpx.AsyncClient(transport=host.GatewayHop(8081, httpx.MockTransport(reply))) as client:
            async with client.stream(
                "POST",
                "https://localhost/v1/chat/completions",
                json=body,
                headers={"authorization": "Bearer synthetic-device-token"},
            ) as response:
                assert b"[DONE]" in await response.aread()
        assert len(seen) == 1 and body["tool_choice"] == "required"

    asyncio.run(run())


def test_study_is_online_only_and_speech_is_not_billed() -> None:
    settings = host.settings_for_browser(Settings(study_offline_enabled=True))
    assert settings.study_workspace_enabled
    assert not settings.study_offline_enabled
    assert settings.cloud_voice_enabled  # spoken turns online through the local gateway (SPEC §6)
    assert settings.study_batch_char_limit == 16000
    assert settings.build_stage == "S3"
    from agent_core.config.support import settings_sections

    sections = {s["id"] for s in settings_sections(settings.build_stage)}
    assert "voice" in sections and not sections & {"parent_summary", "alerts"}  # adults only (JM-D15)


def test_local_model_pin_keeps_cloud_candidates() -> None:
    data = {
        "tiers": {
            "fast": ["local:old", "cloud:primary/fast-model"],
            "strong": ["cloud:primary/strong-model", "local:old"],
        }
    }
    _pin(data, "muse-glimmer")
    assert data["tiers"]["fast"] == ["local:muse-glimmer", "cloud:primary/fast-model"]
    assert data["tiers"]["strong"] == ["local:muse-glimmer", "cloud:primary/strong-model"]


def _gateway(version: str | None, budget: str = "enabled") -> httpx.MockTransport:
    """A gateway answering the host's ping with these headers."""
    headers = {"x-jana-inference-budget": budget}
    if version is not None:
        headers["jana-gateway-version"] = version
    return httpx.MockTransport(lambda request: httpx.Response(204, headers=headers))


def test_the_host_refuses_a_gateway_that_is_not_this_repositorys_on_the_port() -> None:
    """Live-run fix 2026-11-01: a gateway from another project on the shared port answered the ping and knew none
    of this repository's kinds; the host must fail closed, naming the port and the version it found."""
    from cloud_gateway.app import VERSION

    asyncio.run(host.check_gateway(8083, transport=_gateway(VERSION)))  # this repository's gateway passes
    with pytest.raises(ValueError, match=r"port 8083.*serves version 1\.0 .*serves " + VERSION.replace(".", r"\.")):
        asyncio.run(host.check_gateway(8083, transport=_gateway("1.0")))
    with pytest.raises(ValueError, match=r"port 8083.*serves version none"):
        asyncio.run(host.check_gateway(8083, transport=_gateway(None)))
    with pytest.raises(ValueError, match=r"budgeted gateway on port 8083"):
        asyncio.run(host.check_gateway(8083, transport=_gateway(VERSION, budget="disabled")))

    def refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(ValueError, match=r"No gateway answered on port 8083"):
        asyncio.run(host.check_gateway(8083, transport=httpx.MockTransport(refused)))


def test_sponsor_never_grants_consent_and_restart_keeps_credential(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = tmp_path / "gateway.toml"
    original = (REPO_ROOT / "services/cloud-gateway/deploy/meta-dev.toml").read_text()
    config.write_text(original.replace('"~/.jana-meta/gateway"', json.dumps(str(tmp_path / "gateway"))))
    monkeypatch.setenv("JANA_META_GATEWAY_CONFIG", str(config))

    async def available(_port: int) -> None:
        pass

    monkeypatch.setattr(host, "check_gateway", available)

    async def launch(ended: bool = False) -> tuple[str, bytes]:
        runtime = host.SponsoredRuntime(
            host.settings_for_browser(Settings()), REPO_ROOT / "content/agent", REPO_ROOT / "skills", tmp_path / "app"
        )
        runtime.open_stores("0.0.0")
        online = runtime.attach_online()
        assert runtime.directory is not None
        profiles = runtime.directory.summaries()["profiles"]
        if not profiles:
            runtime.directory.create(
                {
                    "display_name": "Synthetic QA",
                    "avatar": "disc-teal",
                    "level": "O",
                    "subjects": ["mathematics"],
                    "age_band": "18_plus",
                }
            )
        core = SimpleNamespace(clock_ms=online.clock_ms, on_profile_created=[], closers=[], components={})
        await host.connect(runtime, cast(CoreService, core))
        held = subscription.load(online.device)
        assert held["allowance_tokens"] == host.monthly_allowance_tokens(runtime.gateway)
        assert held["consent_needed"] and not online.features_on()
        assert held.get("ended_at") is None or ended
        for profile in runtime.directory.summaries()["profiles"]:
            with runtime.directory.open_learner(profile["profile_id"]) as conn:
                assert conn.execute("SELECT count(*) FROM consents").fetchone()[0] == 0
        identity = online.credential.credential_id()
        assert identity is not None
        public = online.credential.public_key()
        if ended:
            held["ended_at"] = online.clock_ms()
            subscription.save(online.device, held, online.clock_ms())
            await host.connect(runtime, cast(CoreService, core))
            assert subscription.load(online.device)["ended_at"] == held["ended_at"]
        for close in core.closers:
            await close()
        await online.client.close()
        await runtime.close()
        return identity, public

    async def run() -> None:
        first = await launch()
        assert await launch(ended=True) == first
        store = GatewayStore(tmp_path / "gateway")
        assert store._db.execute("SELECT count(*) FROM credentials").fetchone()[0] == 1
        assert store._db.execute("SELECT count(*) FROM credentials WHERE revoked_at IS NOT NULL").fetchone()[0] == 0
        store.close()
        assert isinstance(host.SponsoredRuntime(Settings(), Path(), Path(), tmp_path / "app").key_store(), FileKeyStore)

    asyncio.run(run())


def _demo_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, online_demo: bool
) -> tuple[host.SponsoredRuntime, SimpleNamespace]:
    """The host as `hackathon_dev` starts it, before any profile exists; `online_demo` is the flag's environment."""
    config = tmp_path / "gateway.toml"
    original = (REPO_ROOT / "services/cloud-gateway/deploy/meta-dev.toml").read_text()
    config.write_text(original.replace('"~/.jana-meta/gateway"', json.dumps(str(tmp_path / "gateway"))))
    monkeypatch.setenv("JANA_META_GATEWAY_CONFIG", str(config))
    monkeypatch.delenv(host.ONLINE_DEMO, raising=False)
    if online_demo:
        monkeypatch.setenv(host.ONLINE_DEMO, "1")

    async def available(_port: int) -> None:
        pass

    monkeypatch.setattr(host, "check_gateway", available)
    runtime = host.SponsoredRuntime(
        host.settings_for_browser(Settings()), REPO_ROOT / "content/agent", REPO_ROOT / "skills", tmp_path / "app"
    )
    runtime.open_stores("0.0.0")
    online = runtime.attach_online()
    core = SimpleNamespace(
        clock_ms=online.clock_ms,
        on_profile_created=[],
        closers=[],
        components={},
        settings=host.settings_for_browser(Settings()),
        notices={"cloud_tier": ["2026-10-20"], "study_materials": ["2026-10-20"]},
    )
    asyncio.run(host.connect(runtime, cast(CoreService, core)))
    return runtime, core


def _create(runtime: host.SponsoredRuntime, core: SimpleNamespace, name: str, age_band: str) -> str:
    """What `POST /v1/profiles` does: create the profile, then run the hooks."""
    assert runtime.directory is not None
    created = runtime.directory.create(
        {"display_name": name, "avatar": "disc-teal", "level": "O", "subjects": ["physics"], "age_band": age_band}
    )
    for hook in core.on_profile_created:
        hook(created["profile_id"])
    return str(created["profile_id"])


def _learner_state(runtime: host.SponsoredRuntime, profile_id: str) -> dict[str, object]:
    assert runtime.directory is not None and runtime.online is not None
    with runtime.directory.open_learner(profile_id) as conn:
        scopes = {r[0] for r in conn.execute("SELECT scope FROM consents WHERE withdrawn_at IS NULL")}
        return {
            "scopes": scopes,
            "cloud": runtime.online.cloud_effective(profile_id, conn),
            "notices": runtime.online.notice_answer(profile_id),
            "study_notice": runtime.online.notice_answer(profile_id, "study_materials"),
            "memory_online": runtime.online.memory_online_effective(profile_id, conn),
            "features": runtime.online.features_on(),
        }


def test_online_demo_records_the_cloud_tutor_study_and_first_use_notice_for_an_adult(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Demo-host fix 2026-11-01: with the flag, an adult profile created on the host needs no Settings steps."""
    runtime, core = _demo_host(tmp_path, monkeypatch, online_demo=True)
    state = _learner_state(runtime, _create(runtime, core, "Demo Ada", "18_plus"))
    assert state["cloud"] is True and state["notices"] == "accepted" and state["study_notice"] == "accepted"
    assert state["scopes"] == {"cloud_tier", "study_materials"}  # the profile's own consents and no others
    assert state["features"] == {"cloud_tier", "study_materials"}
    assert state["memory_online"] is False  # Personal tutor memory online stays off
    assert state["scopes"].isdisjoint({"tutor_memory_online", "cloud_voice"})  # type: ignore[union-attr]


def test_online_demo_refuses_a_profile_under_18_and_records_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The directory creates adult profiles only (W5), so a minor can be here only from an older build: the band is
    changed under it, as such a build would have stored it, and the grant must refuse."""
    runtime, core = _demo_host(tmp_path, monkeypatch, online_demo=True)
    assert runtime.directory is not None and runtime.online is not None
    created = runtime.directory.create(
        {
            "display_name": "Old Build",
            "avatar": "disc-teal",
            "level": "O",
            "subjects": ["physics"],
            "age_band": "18_plus",
        }
    )
    profile_id = created["profile_id"]
    for band in ("under_13", "13_15", "16_17"):
        with runtime.directory.open_learner(profile_id) as conn:
            conn.execute("UPDATE profile SET age_band = ?", (band,))
            conn.commit()
        with pytest.raises(ValueError, match="adult aged 18 or over"):
            core.on_profile_created[-1](profile_id)  # the hook the flag installed
    assert not runtime.online.features_on()
    state = _learner_state(runtime, profile_id)
    assert state["scopes"] == set() and state["cloud"] is False and state["notices"] is None


def test_without_the_flag_a_new_profile_records_no_consent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The product's consent model is unchanged: nothing is granted unless the host was started with the flag."""
    runtime, core = _demo_host(tmp_path, monkeypatch, online_demo=False)
    state = _learner_state(runtime, _create(runtime, core, "Demo Ada", "18_plus"))
    assert state["scopes"] == set() and state["cloud"] is False and state["notices"] is None
    assert state["features"] == set()


def test_the_flag_is_off_by_default_and_never_inherited_from_the_shell() -> None:
    from jana_tools import hackathon_dev as dev

    shell = {"PATH": "/bin", "META_API_KEY": "x", host.ONLINE_DEMO: "1"}
    plain = dev.host_environment(shell, Path("demo-folder"), 5197, online_demo=False)
    assert host.ONLINE_DEMO not in plain and "META_API_KEY" not in plain
    flagged = dev.host_environment(shell, Path("demo-folder"), 5197, online_demo=True)
    assert flagged[host.ONLINE_DEMO] == "1" and flagged["JANA_DEV_DATA_DIR"] == str(Path("demo-folder").resolve())
