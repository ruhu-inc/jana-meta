"""The hosted demo: the browser app on one server, one isolated core per judge, behind private links.

Each private link belongs to a slot with its own data folder and its own core process, so judges never see each other's
profiles. This process is the only thing a browser reaches: it serves the built app, hands a slot's launch details
only to the browser holding that slot's cookie, and forwards `/core/*` to that slot's core on loopback. The core and
the gateway keep their loopback guards unchanged, and no provider key reaches this process or a core.

    python -m jana_tools.hosted serve --config /etc/jana/hosted.toml
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import shutil
import subprocess
import sys
import tomllib
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import uvicorn
import websockets
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from jana_tools import REPO_ROOT
from jana_tools.hackathon_dev import host_environment

log = logging.getLogger("jana.hosted")

COOKIE = "jana_slot"
COOKIE_DAYS = 14
SLOT_NAME = re.compile(r"^[a-z0-9-]{1,32}$")
MIN_SECRET_LENGTH = 24
# Connection-level headers never cross a proxy (RFC 9110 §7.6.1). Host is set to the loopback the core's guard expects.
HOP_BY_HOP = frozenset({"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailer",
                        "transfer-encoding", "upgrade", "host", "content-length", "cookie"})  # fmt: skip
SEND_STARTED = {"accept-ranges", "cache-control", "content-disposition", "content-language", "content-range",
                "content-type", "etag", "last-modified", "vary", "x-accel-buffering"}  # fmt: skip
SECURITY_HEADERS = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "x-frame-options": "DENY",
}


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Config:
    public_origin: str
    bundle: Path
    data_root: Path
    gateway_config: str
    gateway_port: int
    secure_cookie: bool
    slots: Mapping[str, str]  # slot name to the SHA-256 of its link secret; the secret itself is never stored
    warm: bool = False


def load(path: Path) -> Config:
    raw = tomllib.loads(path.read_text())
    origin = str(raw.get("public_origin", "")).rstrip("/")
    if not re.fullmatch(r"https?://[a-z0-9.:\-\[\]]+", origin):
        raise ConfigError("public_origin must be a bare origin such as https://demo.example.com")
    slots = raw.get("slots")
    if not isinstance(slots, dict) or not slots:
        raise ConfigError("at least one slot is needed")
    for name, digest in slots.items():
        if not SLOT_NAME.fullmatch(name):
            raise ConfigError(f"bad slot name {name!r}")
        if not re.fullmatch(r"[0-9a-f]{64}", str(digest)):
            raise ConfigError(f"slot {name} must hold the SHA-256 of its secret, not the secret")
    return Config(
        public_origin=origin,
        bundle=Path(raw["bundle"]),
        data_root=Path(raw["data_root"]),
        gateway_config=str(raw.get("gateway_config", "services/cloud-gateway/deploy/meta-hosted.toml")),
        gateway_port=int(raw.get("gateway_port", 8081)),
        secure_cookie=origin.startswith("https://"),
        slots=dict(slots),
        warm=bool(raw.get("warm", False)),
    )


def digest(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def slot_for(config: Config, secret: str | None) -> str | None:
    """The slot a link secret or cookie belongs to. Every slot is compared, so timing reveals nothing."""
    if not secret or len(secret) < MIN_SECRET_LENGTH:
        return None
    presented = digest(secret)
    found = None
    for name, expected in config.slots.items():
        if hmac.compare_digest(presented, expected):
            found = name
    return found


def core_environment(config: Config, data_dir: Path, base: Mapping[str, str]) -> dict[str, str]:
    """The desktop host's environment (no provider key in it), pointed at this deployment's gateway. A hosted profile
    starts with the online tutor on, because the landing page has already told the judge where their data goes."""
    env = host_environment(base, data_dir, 0, online_demo=True)
    env["JANA_META_GATEWAY_CONFIG"] = config.gateway_config
    env["JANA_META_GATEWAY_PORT"] = str(config.gateway_port)
    return env


def control_version() -> tuple[int, int]:
    versions = (REPO_ROOT / "scripts" / "jana_tools" / "codegen" / "versions.toml").read_text()
    found = re.search(r'\[interfaces\.control\][\s\S]*?^version\s*=\s*"(\d+)\.(\d+)"', versions, re.M)
    if found is None:
        raise ConfigError("control protocol version is missing")
    return int(found[1]), int(found[2])


@dataclass
class Core:
    """One slot's core process, started the way the desktop shell starts it (ARC-04): the token goes over stdin."""

    name: str
    config: Config
    token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    port: int | None = None
    process: asyncio.subprocess.Process | None = None
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _reader: asyncio.Task[None] | None = None

    @property
    def data_dir(self) -> Path:
        return self.config.data_root / self.name

    def running(self) -> bool:
        return self.port is not None and self.process is not None and self.process.returncode is None

    async def ensure(self) -> None:
        async with self._lock:
            if self.running():
                return
            self.port = None
            self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            process = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "jana_tools.hackathon_app",
                cwd=REPO_ROOT,
                env=core_environment(self.config, self.data_dir, os.environ),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                limit=1024 * 1024,
            )  # fmt: skip
            self.process = process
            major, minor = control_version()
            for message in (
                {"type": "control.hello", "protocol": {"major": major, "minor": minor}},
                {
                    "type": "control.config",
                    "data_dir": str(self.data_dir),
                    "content_root": str(REPO_ROOT / "content" / "agent"),
                    "skills_root": str(REPO_ROOT / "skills"),
                    "release": False,
                    "dev_origins": [self.config.public_origin],
                    "scripted": False,
                },
                {"type": "control.secret", "name": "launch_token", "value": self.token},
            ):
                self._send(message)
            await process.stdin.drain()  # type: ignore[union-attr]
            started: asyncio.Future[int] = asyncio.get_running_loop().create_future()
            self._reader = asyncio.create_task(self._read(process, started))
            self.port = await asyncio.wait_for(started, timeout=180)
            log.warning("slot %s: core ready", self.name)

    def _send(self, message: dict[str, Any]) -> None:
        if self.process is not None and self.process.stdin is not None:
            self.process.stdin.write((json.dumps(message) + "\n").encode())

    async def _read(self, process: asyncio.subprocess.Process, started: asyncio.Future[int]) -> None:
        assert process.stdout is not None
        async for raw in process.stdout:
            try:
                message = json.loads(raw)
            except ValueError:
                continue
            kind = message.get("type")
            if kind == "control.ready" and not started.done():
                started.set_result(int(message["api_port"]))
            elif kind == "control.error":
                log.error("slot %s: core refused to start: %s", self.name, message.get("code"))
                if not started.done():
                    started.set_exception(RuntimeError(str(message.get("code"))))
            elif kind == "control.voice_start":
                # On-device speech packs are a desktop feature; hosted voice goes through the gateway.
                self._send({"type": "control.voice_failed", "request_id": message.get("request_id"),
                            "code": "voice_start_failed"})  # fmt: skip
        if not started.done():
            started.set_exception(RuntimeError(f"core exited {await process.wait()}"))

    async def stop(self) -> None:
        if self.process is None or self.process.returncode is not None:
            return
        self._send({"type": "control.shutdown"})
        try:
            await asyncio.wait_for(self.process.wait(), timeout=15)
        except TimeoutError:
            self.process.kill()


LANDING = (Path(__file__).parent / "hosted_landing.html").read_text()

REFUSED = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Jana</title></head>'
    '<body style="font:16px system-ui;padding:40px">This demo opens from a private link. '
    "Please use the link you were given.</body></html>"
)


async def warm(cores: Mapping[str, Core]) -> None:
    """Start every judge's core ahead of time, one by one, so a first visit does not wait for one to start."""
    for name, core in cores.items():
        try:
            await core.ensure()
        except Exception:  # a first visit tries again and reports it
            log.exception("slot %s: core did not start ahead of time", name)


def create_app(config: Config) -> Starlette:
    cores = {name: Core(name, config) for name in config.slots}
    client = httpx.AsyncClient(trust_env=False, timeout=httpx.Timeout(None, connect=10))
    bundle = config.bundle.resolve()

    def slot_of(request: Request | WebSocket) -> str | None:
        return slot_for(config, request.cookies.get(COOKIE))

    def refused() -> HTMLResponse:
        return HTMLResponse(REFUSED, status_code=403, headers=SECURITY_HEADERS)

    async def link(request: Request) -> Response:
        secret = request.path_params["secret"]
        if slot_for(config, secret) is None:
            return refused()
        response = HTMLResponse(LANDING, headers={**SECURITY_HEADERS, "cache-control": "no-store"})
        response.set_cookie(
            COOKIE, secret, max_age=COOKIE_DAYS * 86400, httponly=True, secure=config.secure_cookie, samesite="lax"
        )
        return response

    async def launch(request: Request) -> Response:
        name = slot_of(request)
        if name is None:
            return JSONResponse({"error": "no_link"}, status_code=403)
        core = cores[name]
        try:
            await core.ensure()
        except Exception:
            log.exception("slot %s: core failed to start", name)
            return JSONResponse({"error": "core_failed"}, status_code=503, headers={"cache-control": "no-store"})
        body = {"base_url": f"{config.public_origin}/core", "token": core.token}
        return JSONResponse(body, headers={"cache-control": "no-store"})

    async def proxy(request: Request) -> Response:
        name = slot_of(request)
        if name is None:
            return JSONResponse({"error": "no_link"}, status_code=403)
        core = cores[name]
        if not core.running():
            return JSONResponse({"error": "core_not_running"}, status_code=503)
        headers = [(k, v) for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP]
        headers.append(("host", f"127.0.0.1:{core.port}"))
        upstream = client.build_request(
            request.method,
            f"http://127.0.0.1:{core.port}/{request.path_params['path']}",
            params=request.url.query.encode() or None,
            headers=headers,
            content=request.stream() if request.method not in ("GET", "HEAD") else None,
        )
        try:
            reply = await client.send(upstream, stream=True)
        except httpx.HTTPError:
            log.warning("slot %s: core did not answer", name)
            return JSONResponse({"error": "core_unreachable"}, status_code=502)

        async def body() -> AsyncIterator[bytes]:
            try:
                async for chunk in reply.aiter_raw():
                    yield chunk
            finally:
                await reply.aclose()

        passed = {k: v for k, v in reply.headers.items() if k.lower() in SEND_STARTED or k.lower().startswith("x-jana")}
        if "content-encoding" in reply.headers:
            passed["content-encoding"] = reply.headers["content-encoding"]
        passed["x-accel-buffering"] = "no"  # streamed answers must reach the page as they are made
        return StreamingResponse(body(), status_code=reply.status_code, headers=passed)

    async def socket(websocket: WebSocket) -> None:
        name = slot_of(websocket)
        if name is None or not cores[name].running():
            await websocket.close(code=4403)
            return
        core = cores[name]
        offered = list(websocket.scope.get("subprotocols", []))
        origin = websocket.headers.get("origin")
        try:
            async with websockets.connect(
                f"ws://127.0.0.1:{core.port}/{websocket.path_params['path']}",
                subprotocols=offered,
                origin=origin,  # type: ignore[arg-type]
                max_size=None,
                proxy=None,
            ) as upstream:
                await websocket.accept(subprotocol=upstream.subprotocol)

                async def up() -> None:
                    while True:
                        message = await websocket.receive()
                        if message["type"] == "websocket.disconnect":
                            return
                        await upstream.send(message["bytes"] if message.get("bytes") is not None else message["text"])

                async def down() -> None:
                    async for message in upstream:
                        if isinstance(message, bytes):
                            await websocket.send_bytes(message)
                        else:
                            await websocket.send_text(message)

                tasks = [asyncio.create_task(up()), asyncio.create_task(down())]
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in tasks:
                    task.cancel()
        except (websockets.WebSocketException, OSError, WebSocketDisconnect):
            log.warning("slot %s: a voice connection closed", name)
        finally:
            with contextlib.suppress(RuntimeError):
                await websocket.close()

    async def asset(request: Request) -> Response:
        if slot_of(request) is None:
            return refused()
        wanted = (bundle / request.path_params["path"]).resolve()
        if wanted.is_file() and wanted.is_relative_to(bundle):
            return FileResponse(wanted, headers=SECURITY_HEADERS)
        return FileResponse(bundle / "index.html", headers={**SECURITY_HEADERS, "cache-control": "no-store"})

    async def healthy(_request: Request) -> Response:
        return JSONResponse({"ok": True})

    async def home(request: Request) -> Response:
        if slot_of(request) is None:
            return refused()
        return FileResponse(bundle / "index.html", headers={**SECURITY_HEADERS, "cache-control": "no-store"})

    @contextlib.asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        warming = asyncio.create_task(warm(cores)) if config.warm else None
        yield
        if warming is not None:
            warming.cancel()
        await asyncio.gather(*(core.stop() for core in cores.values()), return_exceptions=True)
        await client.aclose()

    methods = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    app = Starlette(
        routes=[
            Route("/healthz", healthy),
            Route("/j/{secret}", link),
            Route("/__jana_dev/launch", launch),
            Route("/core/{path:path}", proxy, methods=methods),
            WebSocketRoute("/core/{path:path}", socket),
            Route("/", home),
            Route("/{path:path}", asset),
        ],
        lifespan=lifespan,
    )
    app.state.cores = cores
    return app


def new_links(names: list[str], origin: str) -> tuple[dict[str, str], dict[str, str]]:
    """Fresh secrets: the digests go in the config, and the links are shown once and stored nowhere on the server."""
    digests, links = {}, {}
    for name in names:
        secret = secrets.token_urlsafe(24)
        digests[name] = digest(secret)
        links[name] = f"{origin.rstrip('/')}/j/{secret}"
    return digests, links


def prepare(config: Config, template: Path | None) -> None:
    """Give every slot its packs and, when a template is named, a copy of its saved learner. A slot that already has
    data is left alone, so running this again never overwrites what a judge did."""
    for name in config.slots:
        target = config.data_root / name
        if target.exists():
            print(f"{name}: already prepared")
            continue
        if template is not None:
            shutil.copytree(template, target, symlinks=False)
            forget_sponsor(target)
        else:
            target.mkdir(parents=True, mode=0o700)
        subprocess.run([sys.executable, str(REPO_ROOT / "apps" / "desktop" / "dev" / "seed_packs.py"), str(target)],
                       cwd=REPO_ROOT, check=True)  # fmt: skip
        print(f"{name}: prepared")


def forget_sponsor(data_dir: Path) -> None:
    """A copied learner keeps its work but gets its own online account in this deployment's gateway."""
    import sqlite3

    device = data_dir / "device.db"
    if device.exists():
        with sqlite3.connect(device) as conn:
            conn.execute("DELETE FROM app_settings WHERE key='hackathon_sponsor'")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Run the front door")
    serve.add_argument("--config", type=Path, required=True)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    links = commands.add_parser("links", help="Make new private links: digests for the config, links for you")
    links.add_argument("--origin", required=True)
    links.add_argument("--count", type=int, default=10)
    ready = commands.add_parser("prepare", help="Seed each slot's data folder")
    ready.add_argument("--config", type=Path, required=True)
    ready.add_argument("--template", type=Path)
    args = parser.parse_args()
    if args.command == "links":
        digests, urls = new_links([f"judge-{i + 1}" for i in range(args.count)], args.origin)
        print("[slots]")
        for name, value in digests.items():
            print(f'{name} = "{value}"')
        print("\n# The private links. Keep these out of the server and the repository.", file=sys.stderr)
        for name, url in urls.items():
            print(f"# {name}: {url}", file=sys.stderr)
        return 0
    config = load(args.config)
    if args.command == "prepare":
        prepare(config, args.template)
        return 0
    if not (config.bundle / "index.html").is_file():
        raise ConfigError(f"no built app at {config.bundle}")
    uvicorn.run(create_app(config), host=args.host, port=args.port, log_level="warning", proxy_headers=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
