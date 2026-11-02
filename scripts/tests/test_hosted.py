"""The hosted front door, network-free: a judge's link opens only that judge's slot, and nothing else gets through."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest
from jana_tools import hosted

SECRET = "s" * 32


def _config(tmp_path: Path, **slots: str) -> hosted.Config:
    bundle = tmp_path / "bundle"
    (bundle / "assets").mkdir(parents=True, exist_ok=True)
    (bundle / "index.html").write_text("<title>Jana</title>")
    (bundle / "assets" / "app.js").write_text("app")
    (tmp_path / "secret.txt").write_text("outside")
    return hosted.Config("https://demo.test", bundle, tmp_path / "data", "gateway.toml", 8081, True,
                         slots or {"judge-1": hosted.digest(SECRET)})  # fmt: skip


def _client(app: object, cookie: str | None = None) -> httpx.AsyncClient:
    cookies = {hosted.COOKIE: cookie} if cookie else None
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://demo.test", cookies=cookies)  # type: ignore[arg-type]


def test_a_visitor_with_no_link_gets_nothing(tmp_path: Path) -> None:
    async def run() -> None:
        async with _client(hosted.create_app(_config(tmp_path))) as c:
            for path in ("/", "/assets/app.js", "/some/page"):
                assert (await c.get(path)).status_code == 403
            assert (await c.get("/__jana_dev/launch")).status_code == 403
            assert (await c.get("/core/v1/profiles")).status_code == 403
            assert (await c.post("/core/v1/profiles", json={})).status_code == 403
            assert (await c.get("/healthz")).status_code == 200

    asyncio.run(run())


def test_a_wrong_link_is_refused_and_sets_no_cookie(tmp_path: Path) -> None:
    async def run() -> None:
        async with _client(hosted.create_app(_config(tmp_path))) as c:
            reply = await c.get("/j/" + "x" * 32)
            assert reply.status_code == 403 and "set-cookie" not in reply.headers

    asyncio.run(run())


def test_a_private_link_opens_the_app_and_says_where_data_goes(tmp_path: Path) -> None:
    async def run() -> None:
        async with _client(hosted.create_app(_config(tmp_path))) as c:
            reply = await c.get(f"/j/{SECRET}")
            assert reply.status_code == 200 and "demo server" in reply.text and "this computer" in reply.text
            cookie = reply.headers["set-cookie"].lower()
            assert "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie
            assert reply.headers["cache-control"] == "no-store"
            assert "<title>Jana</title>" in (await c.get("/")).text
            assert (await c.get("/assets/app.js")).text == "app"
            assert "<title>Jana</title>" in (await c.get("/any/route")).text

    asyncio.run(run())


def test_the_app_cannot_read_files_outside_its_bundle(tmp_path: Path) -> None:
    async def run() -> None:
        async with _client(hosted.create_app(_config(tmp_path)), SECRET) as c:
            for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/assets/../../secret.txt"):
                assert "outside" not in (await c.get(path)).text

    asyncio.run(run())


def test_a_slot_needs_the_full_secret(tmp_path: Path) -> None:
    config = _config(tmp_path)
    assert hosted.slot_for(config, SECRET) == "judge-1"
    assert hosted.slot_for(config, SECRET[:-1]) is None
    assert hosted.slot_for(config, None) is None and hosted.slot_for(config, "") is None


def test_two_links_open_two_slots_with_separate_data(tmp_path: Path) -> None:
    other = "t" * 32
    config = _config(tmp_path, **{"judge-1": hosted.digest(SECRET), "judge-2": hosted.digest(other)})
    assert hosted.slot_for(config, SECRET) == "judge-1" and hosted.slot_for(config, other) == "judge-2"
    app = hosted.create_app(config)
    one, two = app.state.cores["judge-1"], app.state.cores["judge-2"]
    assert one.data_dir != two.data_dir and one.token != two.token


def test_no_provider_key_reaches_a_core(tmp_path: Path) -> None:
    base = {"META_API_KEY": "k", "MODEL_API_KEY": "k", "PATH": "/bin", "JANA_ONLINE_DEMO": "0"}
    env = hosted.core_environment(_config(tmp_path), tmp_path, base)
    assert "META_API_KEY" not in env and "MODEL_API_KEY" not in env
    assert env["JANA_ONLINE_DEMO"] == "1" and env["JANA_META_GATEWAY_CONFIG"] == "gateway.toml"


def test_the_config_holds_digests_and_never_a_secret(tmp_path: Path) -> None:
    good = tmp_path / "good.toml"
    digests, links = hosted.new_links(["judge-1"], "https://demo.test/")
    head = 'public_origin = "https://demo.test"\nbundle = "/b"\ndata_root = "/d"\n'
    body = f'{head}[slots]\njudge-1 = "{digests["judge-1"]}"\n'
    good.write_text(body)
    assert hosted.load(good).secure_cookie is True
    assert links["judge-1"].startswith("https://demo.test/j/") and digests["judge-1"] not in links["judge-1"]
    bad = tmp_path / "bad.toml"
    bad.write_text(body.replace(digests["judge-1"], "a-plain-secret"))
    with pytest.raises(hosted.ConfigError):
        hosted.load(bad)


def test_the_hosted_gateway_config_holds_no_key() -> None:
    from cloud_gateway.config import load_config
    from jana_tools import REPO_ROOT

    path = REPO_ROOT / "services" / "cloud-gateway" / "deploy" / "meta-hosted.toml"
    config = load_config(path)
    assert config.environment == "dev" and config.audience_host == "localhost"
    assert config.quotas.device_daily_spend_usd == 5 and config.quotas.deployment_total_spend_usd == 120


def test_cores_start_ahead_of_time_and_one_failure_does_not_stop_the_rest(tmp_path: Path) -> None:
    started: list[str] = []

    class Fake:
        def __init__(self, name: str, fails: bool = False) -> None:
            self.name, self.fails = name, fails

        async def ensure(self) -> None:
            started.append(self.name)
            if self.fails:
                raise RuntimeError("no")

    asyncio.run(hosted.warm({"a": Fake("a", True), "b": Fake("b")}))  # type: ignore[dict-item]
    assert started == ["a", "b"]


def test_warming_is_off_unless_the_config_asks(tmp_path: Path) -> None:
    path = tmp_path / "c.toml"
    digests, _ = hosted.new_links(["judge-1"], "https://demo.test")
    head = 'public_origin = "https://demo.test"\nbundle = "/b"\ndata_root = "/d"\n'
    slots = f'[slots]\njudge-1 = "{digests["judge-1"]}"\n'
    path.write_text(head + slots)
    assert hosted.load(path).warm is False
    path.write_text(head + "warm = true\n" + slots)
    assert hosted.load(path).warm is True
