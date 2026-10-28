"""Start the original browser app with an optional verified, local Muse Glimmer tutor (SPEC §7, JM-D11).

No download happens at launch and no Meta provider key is needed here. The
separately running gateway owns that secret and the persistent inference budget.
With `--local-model` the app keeps tutoring on Muse Glimmer 30B when the gateway
cannot reach Meta (Wi-Fi off): its vision projector and DFlash draft are taken
from the same folder when present.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import secrets
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import httpx

from jana_tools import REPO_ROOT

MODEL = "muse-glimmer-30b"  # the id the router's tiers name (router.yaml)
MODEL_SOURCE = "https://huggingface.co/meta-models/Muse-Glimmer-30B-GGUF"
# Meta publishes no SHA-256, so these were recorded on first download (2026-10-26) against Hugging Face's own hashes
# and are pinned here (SPEC §7).
PINNED_SHA256 = {
    "Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf": "4cc57c0f51040a226e5a72cc47b7613f7772950e460a665f7083de89f183f60e",
    "mmproj-Muse-Glimmer-30B-Q4_K_M.gguf": "f48b452316f9b213758e8659444029b961a24a07f99a1abb2a9f88b06f7c00c6",
    "dflash-Muse-Glimmer-30B-Q4_K_M.gguf": "b2e808bf656086fe86bd0d0bd990f01d33e377537a07c02d45371517c8b264ef",
}
PROJECTOR = "mmproj-Muse-Glimmer-30B-Q4_K_M.gguf"
DRAFT = "dflash-Muse-Glimmer-30B-Q4_K_M.gguf"
# Four slots, one per role whose prompt is long and repeated (coach, solver, diagnoser) and one the short auxiliary
# roles share, so each keeps its prompt prefix cached (llama.py `role_slot`); 8192 tokens each.
SLOTS = 4
CONTEXT = 8192 * SLOTS


def verify_model(path: Path) -> None:
    expected = PINNED_SHA256.get(path.name)
    if expected is None:
        raise ValueError(f"{path.name} is not a pinned Muse Glimmer file")
    with path.open("rb") as source:
        actual = hashlib.file_digest(source, "sha256").hexdigest()
    if actual != expected:
        raise ValueError(f"{path.name} does not match its pinned SHA-256")


def runtime_arguments(model: Path, port: int, key_file: Path) -> list[str]:
    """llama-server's arguments for Glimmer: the GGUF's own chat template (`--jinja`), the vision projector so offline
    photos work, and DFlash speculative decoding (30-45% faster generation on short prompts, SPEC §7). Reasoning is
    left on, as Glimmer requires: the app sets its strength per request."""
    args = ["--model", str(model), "--alias", f"{MODEL},muse-glimmer", "--host", "127.0.0.1", "--port", str(port),
            "--api-key-file", str(key_file), "--ctx-size", str(CONTEXT), "--parallel", str(SLOTS),
            "--n-gpu-layers", "99", "--jinja", "--no-webui", "--log-disable"]  # fmt: skip
    projector, draft = model.with_name(PROJECTOR), model.with_name(DRAFT)
    if projector.is_file():
        args += ["--mmproj", str(projector)]
    if draft.is_file():
        args += ["--model-draft", str(draft), "--spec-type", "draft-dflash", "--n-gpu-layers-draft", "99",
                 "--spec-draft-n-max", "4"]  # fmt: skip
    return args


def stop(child: subprocess.Popen[bytes]) -> None:
    if child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=15)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-model", type=Path)
    parser.add_argument("--port", type=int, default=5187)
    parser.add_argument("--stable", action="store_true", help="Serve a built preview without source-triggered reloads")
    parser.add_argument("--data-dir", type=Path, default=Path(tempfile.gettempdir()) / "jana-meta-browser")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    # Only the gateway may hold a provider key: none reaches the app, its core or the local model runtime, so every
    # `*_API_KEY` in the shell (META_API_KEY, Meta's MODEL_API_KEY, NVIDIA_API_KEY, any other) is left out.
    env = {key: value for key, value in os.environ.items() if not key.upper().endswith("_API_KEY")}
    env.update(
        JANA_META_GATEWAY_CONFIG="services/cloud-gateway/deploy/meta-dev.toml",
        JANA_DEV_DATA_DIR=str(args.data_dir.resolve()),
        JANA_DEV_HOST="127.0.0.1",
        PORT=str(args.port),
    )
    pnpm = shutil.which("pnpm")
    if not pnpm:
        parser.error("pnpm is not installed")
    with tempfile.TemporaryDirectory(prefix="jana-meta-runtime-") as folder:
        runtime = None
        try:
            if args.local_model:
                model = args.local_model.resolve()
                for path in (model, model.with_name(PROJECTOR), model.with_name(DRAFT)):
                    if path == model or path.is_file():
                        verify_model(path)
                program = shutil.which("llama-server")
                if not program:
                    parser.error("Install llama.cpp before selecting the local Muse Glimmer model")
                with socket.socket() as sock:
                    sock.bind(("127.0.0.1", 0))
                    port = sock.getsockname()[1]
                key = secrets.token_urlsafe(32)
                key_file = Path(folder) / "runtime.key"
                key_file.touch(mode=0o600)
                key_file.write_text(key)
                runtime = subprocess.Popen([program, *runtime_arguments(model, port, key_file)], cwd=REPO_ROOT, env=env)
                endpoint = f"http://127.0.0.1:{port}"
                with httpx.Client(trust_env=False, headers={"authorization": f"Bearer {key}"}) as client:
                    deadline = time.monotonic() + 300  # 17 GB read from a cold disk
                    while time.monotonic() < deadline:
                        if runtime.poll() is not None:
                            raise RuntimeError("The local Muse Glimmer runtime exited during loading")
                        try:
                            if client.get(endpoint + "/health", timeout=2).status_code == 200:
                                break
                        except httpx.HTTPError:
                            pass
                        time.sleep(0.5)
                    else:
                        raise RuntimeError("The local Muse Glimmer runtime did not load within five minutes")
                # Native control.runtime_endpoint performs the real tool-template
                # readiness generation; /health above only sequences startup.
                env["JANA_DEV_RUNTIME"] = f"{endpoint} {key} {MODEL}"
                print("Verified Muse Glimmer 30B loaded locally; native readiness check follows.", flush=True)
            command = [pnpm, "--filter", "@jana/desktop", "dev"]
            if args.stable:
                bundle = str(Path(folder) / "browser")
                subprocess.run(
                    [pnpm, "--filter", "@jana/desktop", "exec", "vite", "build", "--outDir", bundle],
                    cwd=REPO_ROOT,
                    env=env,
                    check=True,
                )
                command = [
                    pnpm,
                    "--filter",
                    "@jana/desktop",
                    "exec",
                    "vite",
                    "preview",
                    "--outDir",
                    bundle,
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(args.port),
                    "--strictPort",
                ]
            app = subprocess.Popen(command, cwd=REPO_ROOT, env=env)
            try:
                return app.wait()
            finally:
                stop(app)
        except KeyboardInterrupt:
            return 130
        finally:
            if runtime is not None:
                stop(runtime)


if __name__ == "__main__":
    raise SystemExit(main())
