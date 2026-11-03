#!/usr/bin/env bash
# Runs on the VM as root, from the VM's startup script. Safe to run again: a judge's data is never overwritten.
set -euo pipefail
exec > >(tee -a /var/log/jana-setup.log) 2>&1
meta() { curl -fsS -H 'Metadata-Flavor: Google' "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"; }
COMMIT=$(meta jana-commit)
HOSTNAME_PUBLIC=$(meta jana-host)
REPO=https://github.com/ruhu-inc/jana-meta.git
NODE=24.21.0
UV=0.10.9

apt-get update -qq
apt-get install -y -qq --no-install-recommends ca-certificates curl git xz-utils bubblewrap tesseract-ocr ffmpeg \
  espeak-ng libgomp1 caddy sqlite3 > /dev/null
if [ ! -x /usr/local/bin/node ] || [ "$(/usr/local/bin/node -v)" != "v$NODE" ]; then
  curl -fsSL "https://nodejs.org/dist/v$NODE/node-v$NODE-linux-x64.tar.xz" | tar -xJ -C /usr/local --strip-components=1
fi
corepack enable
export COREPACK_ENABLE_DOWNLOAD_PROMPT=0 TURBO_TELEMETRY_DISABLED=1
if ! command -v uv > /dev/null || [ "$(uv --version | cut -d' ' -f2)" != "$UV" ]; then
  curl -LsSf "https://astral.sh/uv/$UV/install.sh" | env UV_INSTALL_DIR=/usr/local/bin INSTALLER_NO_MODIFY_PATH=1 sh
fi

id jana > /dev/null 2>&1 || useradd --system --home-dir /var/lib/jana --create-home --shell /usr/sbin/nologin jana
install -d -o jana -g jana -m 0700 /var/lib/jana /var/lib/jana/gateway /var/lib/jana/data
install -d -o jana -g jana -m 0755 /opt/jana
install -d -m 0700 /etc/jana

run_as() { sudo -u jana -H env PATH="$PATH" COREPACK_ENABLE_DOWNLOAD_PROMPT=0 TURBO_TELEMETRY_DISABLED=1 "$@"; }
[ -d /opt/jana/app/.git ] || run_as git clone --quiet "$REPO" /opt/jana/app
run_as git -C /opt/jana/app fetch --quiet origin
run_as git -C /opt/jana/app -c advice.detachedHead=false checkout --quiet "$COMMIT"
cd /opt/jana/app
run_as uv sync --locked --all-packages --quiet
run_as pnpm install --frozen-lockfile --silent
run_as env VITE_JANA_HOSTED=1 pnpm --filter @jana/desktop exec vite build --outDir /opt/jana/bundle --emptyOutDir

meta jana-slots > /etc/jana/slots.toml
cat > /etc/jana/hosted.toml <<CONFIG
public_origin = "https://$HOSTNAME_PUBLIC"
bundle = "/opt/jana/bundle"
data_root = "/var/lib/jana/data"
gateway_config = "services/cloud-gateway/deploy/meta-hosted.toml"
gateway_port = 8081
warm = true
member_slots = 10
accounts_db = "/var/lib/jana/accounts.sqlite3"
CONFIG
# Google sign-in stays off until deploy.sh is given a client id and its secret is in Secret Manager.
google_client=$(meta jana-google-client-id 2>/dev/null || true)
if [ -n "$google_client" ]; then
  gcloud secrets versions access latest --secret=jana-google-client-secret > /etc/jana/google_client_secret
  chown root:jana /etc/jana/google_client_secret
  chmod 0640 /etc/jana/google_client_secret
  printf 'google_client_id = "%s"\ngoogle_secret_file = "/etc/jana/google_client_secret"\n' "$google_client" >> /etc/jana/hosted.toml
fi
cat /etc/jana/slots.toml >> /etc/jana/hosted.toml
chown root:jana /etc/jana /etc/jana/hosted.toml
chmod 0750 /etc/jana
chmod 0640 /etc/jana/hosted.toml

# deploy.sh uploads the saved learner while this runs, and writes .complete last: wait for it, or slots start empty.
template=()
if [ "$(meta jana-template)" = "yes" ]; then
  for _ in $(seq 1 180); do [ -f /var/lib/jana/template/.complete ] && break; sleep 10; done
  [ -f /var/lib/jana/template/.complete ] || { echo "the saved learner never arrived"; exit 1; }
  template=(--template /var/lib/jana/template)
fi
run_as .venv/bin/python -m jana_tools.hosted prepare --config /etc/jana/hosted.toml "${template[@]}"

cat > /etc/caddy/Caddyfile <<CADDY
$HOSTNAME_PUBLIC {
  encode zstd gzip
  reverse_proxy 127.0.0.1:8000 {
    flush_interval -1
  }
}
CADDY
install -m 0644 scripts/hosted/jana-key.service scripts/hosted/jana-gateway.service scripts/hosted/jana-front.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --quiet jana-key jana-gateway jana-front caddy
systemctl restart jana-key jana-gateway
sleep 3
systemctl restart jana-front caddy
touch /var/lib/jana/.setup-done
echo "jana setup finished at $COMMIT"
