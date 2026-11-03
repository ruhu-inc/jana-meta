"""Hosted sign-in, network-free: no invite, no account; each account keeps to its own slot; secrets stay hashed."""

from __future__ import annotations

import asyncio
import base64
import json
import sqlite3
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from jana_tools import hosted
from jana_tools.hosted_accounts import AccountError, Accounts, Attempts, hash_password, verify_password

ORIGIN = "https://demo.test"
LINK = "s" * 32
INVITE = "abc123-def456-789abc"
PASSWORD = "correct horse battery"  # noqa: S105 -- a test value


def config(tmp_path: Path, members: int = 2, invite: str | None = INVITE, google: bool = False) -> hosted.Config:
    bundle = tmp_path / "bundle"
    (bundle / "assets").mkdir(parents=True, exist_ok=True)
    (bundle / "index.html").write_text("<title>Jana</title>")
    (bundle / "assets" / "app.js").write_text("app")
    secret = tmp_path / "google_secret"
    secret.write_text("google-client-secret")
    return hosted.Config(
        ORIGIN, bundle, tmp_path / "data", "gateway.toml", 8081, True, {"judge-1": hosted.digest(LINK)},
        member_slots=members, accounts_db=tmp_path / "accounts.sqlite3",
        invite_digest=hosted.digest(invite) if invite else None,
        google_client_id="client-id" if google else None, google_secret_file=secret if google else None,
    )  # fmt: skip


def client(app: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=ORIGIN, headers={"origin": ORIGIN})


def run(body: Callable[[], Awaitable[None]]) -> None:
    asyncio.run(body())  # type: ignore[arg-type]


async def signup(
    c: httpx.AsyncClient, email: str = "ada@example.com", invite: str = INVITE, password: str = PASSWORD
) -> httpx.Response:
    return await c.post("/signup", data={"invite": invite, "email": email, "password": password})


def test_a_stranger_reaches_only_the_sign_in_page(tmp_path: Path) -> None:
    async def body() -> None:
        async with client(hosted.create_app(config(tmp_path))) as c:
            for path in ("/", "/some/page", "/welcome", "/account"):
                reply = await c.get(path)
                assert reply.status_code == 303 and reply.headers["location"] == "/signin"
            assert (await c.get("/assets/app.js")).status_code == 403
            assert (await c.get("/__jana_dev/launch")).status_code == 403
            assert (await c.get("/core/v1/study/workspace")).status_code == 403
            assert (await c.post("/core/v1/study/jobs", json={})).status_code == 403
            assert "Sign in" in (await c.get("/signin")).text

    run(body)


def test_sign_up_needs_the_invite_code(tmp_path: Path) -> None:
    async def body() -> None:
        app = hosted.create_app(config(tmp_path))
        async with client(app) as c:
            for code in ("wrong-code", "", " "):
                reply = await signup(c, invite=code)
                assert reply.status_code == 403 and "invite code" in reply.text
                assert hosted.SESSION_COOKIE not in c.cookies
            assert (await c.get("/")).status_code == 303
        assert Accounts(tmp_path / "accounts.sqlite3", []).listed() == []

    run(body)


def test_sign_up_is_closed_with_no_code_configured(tmp_path: Path) -> None:
    async def body() -> None:
        async with client(hosted.create_app(config(tmp_path, invite=None))) as c:
            assert "closed" in (await c.get("/signup")).text
            assert (await signup(c)).status_code == 403

    run(body)


def test_sign_up_then_in_and_out(tmp_path: Path) -> None:
    async def body() -> None:
        async with client(hosted.create_app(config(tmp_path))) as c:
            reply = await signup(c)
            assert reply.status_code == 303 and reply.headers["location"] == "/welcome"
            cookie = reply.headers["set-cookie"].lower()
            assert "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie
            assert (await c.get("/")).text == "<title>Jana</title>"
            assert "ada@example.com" in (await c.get("/account")).text
            token = c.cookies[hosted.SESSION_COOKIE]
            assert (await c.post("/signout")).status_code == 303
            c.cookies.delete(hosted.SESSION_COOKIE)
            assert (await c.get("/")).status_code == 303
            c.cookies.set(hosted.SESSION_COOKIE, token, domain="demo.test")  # a stolen, ended session opens nothing
            assert (await c.get("/")).status_code == 303
            c.cookies.delete(hosted.SESSION_COOKIE)
            assert (
                await c.post("/signin", data={"email": "ada@example.com", "password": "not the password"})
            ).status_code == 401
            reply = await c.post("/signin", data={"email": "ADA@example.com ", "password": PASSWORD})
            assert reply.status_code == 303 and reply.headers["location"] == "/"
            assert (await c.get("/")).status_code == 200

    run(body)


def test_a_wrong_address_and_a_wrong_password_read_the_same(tmp_path: Path) -> None:
    async def body() -> None:
        async with client(hosted.create_app(config(tmp_path))) as c:
            await signup(c)
            c.cookies.clear()
            one = await c.post("/signin", data={"email": "ada@example.com", "password": "wrong password"})
            two = await c.post("/signin", data={"email": "nobody@example.com", "password": "wrong password"})
            assert one.status_code == two.status_code == 401 and one.text == two.text

    run(body)


def test_two_accounts_get_two_slots_and_the_places_run_out(tmp_path: Path) -> None:
    async def body() -> None:
        async with client(hosted.create_app(config(tmp_path))) as c:
            for email in ("a@example.com", "b@example.com"):
                c.cookies.clear()
                assert (await signup(c, email)).status_code == 303
            c.cookies.clear()
            full = await signup(c, "c@example.com")
            assert full.status_code == 400 and "places are taken" in full.text
            c.cookies.clear()
            again = await signup(c, "a@example.com")
            assert again.status_code == 400 and "already an account" in again.text
        listed = Accounts(tmp_path / "accounts.sqlite3", []).listed()
        assert [a.slot for a in listed] == ["member-1", "member-2"]

    run(body)


def test_an_account_opens_only_its_own_core(tmp_path: Path) -> None:
    async def body() -> None:
        app = hosted.create_app(config(tmp_path))
        started: list[str] = []
        for core in app.state.cores.values():

            async def ensure(core: hosted.Core = core) -> None:
                started.append(core.name)

            core.ensure = ensure  # type: ignore[method-assign]
        async with client(app) as c:
            await signup(c, "a@example.com")
            one = (await c.get("/__jana_dev/launch")).json()
            c.cookies.clear()
            await signup(c, "b@example.com")
            two = (await c.get("/__jana_dev/launch")).json()
        assert started == ["member-1", "member-2"] and one["token"] != two["token"]
        assert app.state.cores["member-1"].token == one["token"]

    run(body)


def test_private_links_still_open_their_own_slot(tmp_path: Path) -> None:
    async def body() -> None:
        async with client(hosted.create_app(config(tmp_path))) as c:
            assert (await c.get(f"/j/{LINK}")).status_code == 200
            assert (await c.get("/")).status_code == 200

    run(body)


def test_another_site_cannot_post_to_the_forms(tmp_path: Path) -> None:
    async def body() -> None:
        transport = httpx.ASGITransport(app=hosted.create_app(config(tmp_path)))
        async with httpx.AsyncClient(
            transport=transport, base_url=ORIGIN, headers={"origin": "https://evil.test"}
        ) as c:
            assert (await signup(c)).status_code == 403
            assert (await c.post("/signin", data={"email": "a@example.com", "password": PASSWORD})).status_code == 403
            assert (await c.post("/signout")).status_code == 403

    run(body)


def test_guessing_is_slowed_for_an_address_and_a_visitor(tmp_path: Path) -> None:
    async def body() -> None:
        async with client(hosted.create_app(config(tmp_path))) as c:
            await signup(c)
            c.cookies.clear()
            codes = [
                (await c.post("/signin", data={"email": "ada@example.com", "password": f"guess number {i}"},
                              headers={"x-forwarded-for": f"10.0.0.{i}"})).status_code
                for i in range(9)
            ]  # fmt: skip
            assert codes[:8] == [401] * 8 and codes[8] == 429
            right = await c.post(
                "/signin",
                data={"email": "ada@example.com", "password": PASSWORD},
                headers={"x-forwarded-for": "10.0.0.99"},
            )
            assert right.status_code == 429

    run(body)


def test_sign_ups_are_limited_per_visitor(tmp_path: Path) -> None:
    async def body() -> None:
        async with client(hosted.create_app(config(tmp_path))) as c:
            codes = [(await signup(c, invite="wrong")).status_code for _ in range(6)]
            assert codes == [403] * 5 + [429]

    run(body)


def test_only_digests_are_stored(tmp_path: Path) -> None:
    async def body() -> None:
        async with client(hosted.create_app(config(tmp_path))) as c:
            await signup(c)
            token = c.cookies[hosted.SESSION_COOKIE]
        raw = (tmp_path / "accounts.sqlite3").read_bytes()
        assert PASSWORD.encode() not in raw and token.encode() not in raw and INVITE.encode() not in raw
        assert (tmp_path / "accounts.sqlite3").stat().st_mode & 0o077 == 0
        with sqlite3.connect(tmp_path / "accounts.sqlite3") as conn:
            assert conn.execute("SELECT password_hash FROM accounts").fetchone()[0].startswith("scrypt$")

    run(body)


def test_passwords_are_checked_properly() -> None:
    stored = hash_password(PASSWORD)
    assert verify_password(PASSWORD, stored) and not verify_password("wrong password", stored)
    assert not verify_password(PASSWORD, None)
    assert hash_password(PASSWORD) != stored
    with pytest.raises(AccountError):
        hash_password("short")


def test_resetting_a_password_ends_sessions(tmp_path: Path) -> None:
    store = Accounts(tmp_path / "a.sqlite3", ["member-1"])
    account = store.create("a@example.com", hash_password(PASSWORD))
    token = store.start_session(account.account_id)
    assert store.from_session(token) == account
    assert store.set_password("a@example.com", hash_password("another good password"))
    assert store.from_session(token) is None
    assert not store.set_password("nobody@example.com", hash_password("another good password"))


def test_attempts_recover_after_the_window() -> None:
    limit = Attempts(1, 10)
    assert limit.allow("k", 0) and not limit.allow("k", 5) and limit.allow("k", 11)


# --- Google, against a stand-in for its token endpoint -------------------------------------------------------------


def id_token(**changes: Any) -> str:
    claims = {"iss": "https://accounts.google.com", "aud": "client-id", "sub": "g-1", "email": "ada@example.com",
              "email_verified": True, "exp": time.time() + 600, **changes}  # fmt: skip
    encode = lambda value: base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")  # noqa: E731
    return f"{encode({'alg': 'none'})}.{encode(claims)}.sig"


def google_app(tmp_path: Path, token: str | None, status: int = 200) -> tuple[Any, list[dict[str, str]]]:
    calls: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(dict(p.split("=", 1) for p in request.content.decode().split("&")))
        return httpx.Response(status, json={"id_token": token} if token else {})

    return hosted.create_app(config(tmp_path, google=True), google_transport=httpx.MockTransport(handler)), calls


async def through_google(c: httpx.AsyncClient, invite: str | None = INVITE) -> httpx.Response:
    start = await (c.post("/auth/google/start", data={"invite": invite}) if invite else c.get("/auth/google"))
    assert start.status_code == 303, start.text
    state = dict(p.split("=", 1) for p in start.headers["location"].split("?")[1].split("&"))["state"]
    return await c.get(f"/auth/google/callback?state={state}&code=the-code")


def test_google_sign_up_needs_the_invite_too(tmp_path: Path) -> None:
    async def body() -> None:
        app, _ = google_app(tmp_path, id_token())
        async with client(app) as c:
            assert (await c.post("/auth/google/start", data={"invite": "wrong"})).status_code == 403
            refused = await through_google(c, invite=None)  # the sign-in button, with no account yet
            assert refused.status_code == 403 and hosted.SESSION_COOKIE not in c.cookies
            made = await through_google(c)
            assert made.status_code == 303 and made.headers["location"] == "/welcome"
            assert (await c.get("/")).status_code == 200
            c.cookies.delete(hosted.SESSION_COOKIE)
            back = await through_google(c, invite=None)
            assert back.status_code == 303 and back.headers["location"] == "/"
        assert [a.email for a in Accounts(tmp_path / "accounts.sqlite3", []).listed()] == ["ada@example.com"]

    run(body)


def test_google_joins_an_existing_account_with_the_same_proved_address(tmp_path: Path) -> None:
    async def body() -> None:
        app, _ = google_app(tmp_path, id_token())
        async with client(app) as c:
            await signup(c)
            c.cookies.delete(hosted.SESSION_COOKIE)
            assert (await through_google(c, invite=None)).status_code == 303
        listed = Accounts(tmp_path / "accounts.sqlite3", []).listed()
        assert len(listed) == 1 and listed[0].google and listed[0].has_password

    run(body)


@pytest.mark.parametrize("bad", [
    {"aud": "another-app"}, {"iss": "https://evil.test"}, {"email_verified": False}, {"exp": 1}, {"sub": ""},
])  # fmt: skip
def test_a_google_token_that_fails_any_check_signs_nobody_in(tmp_path: Path, bad: dict[str, Any]) -> None:
    async def body() -> None:
        app, _ = google_app(tmp_path, id_token(**bad))
        async with client(app) as c:
            reply = await through_google(c)
            assert reply.status_code == 400 and hosted.SESSION_COOKIE not in c.cookies

    run(body)


def test_google_refusing_the_code_signs_nobody_in(tmp_path: Path) -> None:
    async def body() -> None:
        app, _ = google_app(tmp_path, None, status=400)
        async with client(app) as c:
            assert (await through_google(c)).status_code == 400

    run(body)


def test_a_forged_or_replayed_callback_is_refused(tmp_path: Path) -> None:
    async def body() -> None:
        app, calls = google_app(tmp_path, id_token())
        async with client(app) as c:
            assert (await c.get("/auth/google/callback?state=made-up&code=x")).status_code == 400
            start = await c.post("/auth/google/start", data={"invite": INVITE})
            state = dict(p.split("=", 1) for p in start.headers["location"].split("?")[1].split("&"))["state"]
            c.cookies.delete(hosted.STATE_COOKIE)  # another browser, without the state cookie
            assert (await c.get(f"/auth/google/callback?state={state}&code=x")).status_code == 400
            assert (
                await c.get(f"/auth/google/callback?state={state}&code=x")
            ).status_code == 400  # and it is single-use
        assert calls == []

    run(body)


def test_google_stays_hidden_until_configured(tmp_path: Path) -> None:
    async def body() -> None:
        async with client(hosted.create_app(config(tmp_path))) as c:
            assert "Google" not in (await c.get("/signin")).text and "Google" not in (await c.get("/signup")).text
            assert (await c.get("/auth/google")).status_code == 403

    run(body)
