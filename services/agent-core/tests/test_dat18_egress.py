"""DAT-18 shipping egress audit. TLS services, profile content and consent/signing material are synthetic."""

import asyncio
import json
import subprocess
from pathlib import Path

import pytest
from agent_core.contracts import errors
from agent_core.net import crash_reports
from agent_core.net.policy import EgressRefused, load_policy
from agent_core.net.redaction import Redactor
from agent_core.providers.base import Message, ProviderError
from agent_core.providers.gateway import GatewayProvider
from jana_tools import REPO_ROOT
from net_harness import FakeServices, enable, layer, telemetry_payload


@pytest.mark.parametrize("feature", sorted(load_policy().features))
def dat18_egress_field_allowlist(tmp_path: Path, feature: str):
    row = load_policy().features[feature]
    if feature in {"downloads", "update_checks"}:
        # Execute the shell's actual request builders / captured TLS requests, rather than duplicate them in Python.
        case = (
            "download_http::tests::https_ranges_redirects_and_pin_failures"
            if feature == "downloads"
            else "updates::tests::plt14_no_checks_when_off"
        )
        done = subprocess.run(
            ["cargo", "test", "--offline", "--lib", case, "--", "--exact"],
            cwd=REPO_ROOT / "apps/desktop/src-tauri",
            text=True,
            capture_output=True,
            timeout=180,
        )
        assert done.returncode == 0, done.stdout + done.stderr
        assert "1 passed" in done.stdout, done.stdout
        return

    async def scenario():
        async with FakeServices(tmp_path) as fake:
            online = layer(tmp_path, fake)
            try:
                enable(online, feature)
                online.connectivity.state = "online"
                if row.stage != "S2":
                    with pytest.raises(EgressRefused, match="stage_not_shipped"):
                        await online.client.send(
                            feature,
                            "POST",
                            f"https://{online.host_for(feature)}/v1/x",
                            row.payload_classes[0],
                            body={"private_note": "MUST-STAY-LOCAL"},
                        )
                    assert fake.requests == []
                    return
                if feature == "cloud_tier":
                    online.record_notice("prf_private", feature, True)
                    provider = GatewayProvider(
                        online.client,
                        lambda: online.host_for(feature),
                        "primary",
                        redactor=Redactor(("MUST-STAY-LOCAL",)),
                        profile_id="prf_private",
                    )
                    await provider.complete("fast", [Message("user", "What is speed?")], [])
                    before = len(fake.requests)
                    with pytest.raises(ProviderError):
                        await provider.complete("fast", [Message("user", "MUST-STAY-LOCAL")], [])
                    assert len(fake.requests) == before
                    sent = fake.requests[-1]
                    assert errors("cloud/gateway#/$defs/ChatCompletionRequest", sent.json()) == []
                    assert sent.json()["messages"] == [{"role": "user", "content": "What is speed?"}]
                    assert sent.headers["x-session-pseudonym"] == provider.pseudonym
                elif feature == "tutor_memory_online":
                    # SPEC §19.6 (W8): the row's fields are the cloud tier's chat request; what it adds is the
                    # cloud_notes block, scrubbed. A note naming a profile term stays on the device.
                    from agent_core.config import Settings
                    from agent_core.memory.render import fit_block
                    from agent_core.memory.snapshot import freeze
                    from agent_core.store.ids import new_ulid
                    from memory_harness import DAY, PACK, store

                    held = store()
                    kept = held.note("Divides distance by time correctly", new_ulid())
                    private = held.note("Learns graphs best through the zorblat method", new_ulid())  # a profile term
                    settings = Settings()
                    frozen = freeze(held.conn, PACK, settings, subject="physics", topic_id=None, session_date=DAY)
                    block = fit_block(frozen, variant="cloud_notes", allowance_chars=4000, settings=settings,
                                      terms=("zorblat",))  # fmt: skip
                    assert block.withheld_note_ids == (private,) and block.shown_note_ids == (kept,)
                    enable(online, "cloud_tier")  # the consent requires the cloud tier; its requests ride it
                    online.record_notice("prf_private", "cloud_tier", True)
                    provider = GatewayProvider(online.client, lambda: online.host_for("cloud_tier"), "primary",
                                               redactor=Redactor(("MUST-STAY-LOCAL",)),
                                               profile_id="prf_private")  # fmt: skip
                    await provider.complete("strong", [Message("system", block.text), Message("user", "Reflect.")],
                                            [], role="reflector")  # fmt: skip
                    sent = fake.requests[-1]
                    assert errors("cloud/gateway#/$defs/ChatCompletionRequest", sent.json()) == []
                    assert sent.headers["x-jana-role"] == "reflector"
                    assert "Divides distance by time correctly" in sent.json()["messages"][0]["content"]
                    assert "zorblat" not in json.dumps(sent.json())
                elif feature == "telemetry":
                    good = json.loads(telemetry_payload())
                    with pytest.raises(ValueError):
                        online.outbox.put(
                            "telemetry",
                            feature,
                            json.dumps({**good, "note": "MUST-STAY-LOCAL"}).encode(),
                            expires_ms=10**15,
                        )
                    online.outbox.put("telemetry", feature, json.dumps(good).encode(), expires_ms=10**15)
                    assert await online.outbox.drain(force=True) == 1
                    assert errors("trace/telemetry", fake.requests[-1].json()) == []
                else:
                    seeded = {
                        "crash_id": "crs_synthetic",
                        "process": "core",
                        "kind": "exception",
                        "version": "0.0.0",
                        "note": "MUST-STAY-LOCAL",
                        "transcript": "MUST-STAY-LOCAL",
                        "stack": [],
                        "log_tail": [],
                    }
                    report = online.crash_report(seeded, "low")
                    online.send_crash_report(report, ["MUST-STAY-LOCAL"], 10**15)
                    with pytest.raises(crash_reports.CrashReportRefused):
                        online.send_crash_report({**report, "note": "MUST-STAY-LOCAL"}, [], 10**15)
                    assert await online.outbox.drain(force=True) == 1
                    assert errors(crash_reports.CONTRACT, fake.requests[-1].json()) == []
                wire = json.dumps([r.json() for r in fake.requests]) + json.dumps([r.headers for r in fake.requests])
                assert "MUST-STAY-LOCAL" not in wire and "prf_private" not in wire
                if feature not in ("cloud_tier", "tutor_memory_online"):
                    assert all("authorization" not in r.headers and "cookie" not in r.headers for r in fake.requests)
            finally:
                await online.stop()

    asyncio.run(scenario())
