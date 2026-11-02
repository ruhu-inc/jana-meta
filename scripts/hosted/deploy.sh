#!/usr/bin/env bash
# Creates or updates the hosted demo in one GCP project. Reads no key: you add it to Secret Manager yourself.
#   scripts/hosted/deploy.sh PROJECT_ID [--zone ZONE] [--domain NAME] [--commit SHA] [--judges N] [--template DIR]
set -euo pipefail
project=${1:?usage: deploy.sh PROJECT_ID [--zone ZONE] [--domain NAME] [--commit SHA] [--judges N] [--template DIR]}; shift
domain="" commit="" judges=10 template="" zone=europe-west1-b # Belgium
while (($#)); do
  case "$1" in
    --zone) zone=$2; shift 2 ;;
    --domain) domain=$2; shift 2 ;;
    --commit) commit=$2; shift 2 ;;
    --judges) judges=$2; shift 2 ;;
    --template) template=$2; shift 2 ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
done
here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../.." && pwd)
region=${zone%-*} vm=jana-demo
gc() { gcloud --project "$project" --quiet "$@"; }
[ -n "$commit" ] || commit=$(git -C "$repo" rev-parse origin/main)
git -C "$repo" merge-base --is-ancestor "$commit" origin/main || { echo "$commit is not on origin/main, which the VM clones" >&2; exit 2; }

gc services enable compute.googleapis.com secretmanager.googleapis.com > /dev/null
if ! gc secrets versions list jana-meta-api-key --limit 1 --format='value(name)' 2>/dev/null | grep -q .; then
  gc secrets create jana-meta-api-key --replication-policy=automatic 2> /dev/null || true
  cat <<HELP
Add the Meta key to Secret Manager, then run this script again. On macOS, from the keychain:

  security find-generic-password -s jana-meta.cloud-gateway -a meta_api_key -w | tr -d '\n' | gcloud --project $project secrets versions add jana-meta-api-key --data-file=-
HELP
  exit 3
fi

account=jana-demo@$project.iam.gserviceaccount.com
gc iam service-accounts describe "$account" > /dev/null 2>&1 || gc iam service-accounts create jana-demo --display-name "Jana hosted demo" > /dev/null
gc secrets add-iam-policy-binding jana-meta-api-key --member "serviceAccount:$account" --role roles/secretmanager.secretAccessor > /dev/null
gc compute addresses describe jana-demo --region "$region" > /dev/null 2>&1 || gc compute addresses create jana-demo --region "$region" > /dev/null
address=$(gc compute addresses describe jana-demo --region "$region" --format='value(address)')
host=${domain:-${address//./-}.sslip.io}
gc compute firewall-rules describe jana-demo-web > /dev/null 2>&1 || gc compute firewall-rules create jana-demo-web --allow tcp:80,tcp:443 --target-tags jana-demo > /dev/null

# Private links are made once, here, and kept out of the VM and the repository.
state=${JANA_HOSTED_STATE:-$HOME/.jana-hosted/$project}
mkdir -p "$state"; chmod 700 "$state"
if [ ! -f "$state/slots.toml" ] || ! grep -q "$host" "$state/links.txt" 2> /dev/null; then
  (cd "$repo" && uv run --frozen --offline python -m jana_tools.hosted links --origin "https://$host" --count "$judges") > "$state/slots.toml" 2> "$state/links.txt"
fi
chmod 600 "$state/slots.toml" "$state/links.txt"

wanted=no; [ -n "$template" ] && wanted=yes
metadata=(--metadata "jana-commit=$commit,jana-host=$host,jana-template=$wanted" --metadata-from-file "jana-slots=$state/slots.toml,startup-script=$here/startup.sh")
if gc compute instances describe "$vm" --zone "$zone" > /dev/null 2>&1; then
  gc compute instances add-metadata "$vm" --zone "$zone" "${metadata[@]}" > /dev/null
else
  gc compute instances create "$vm" --zone "$zone" --machine-type e2-standard-8 --image-family debian-12 \
    --image-project debian-cloud --boot-disk-size 100GB --boot-disk-type pd-balanced --address "$address" \
    --tags jana-demo --service-account "$account" --scopes cloud-platform --labels app=jana-meta,purpose=hackathon \
    "${metadata[@]}" > /dev/null
fi
if [ -n "$template" ]; then
  until gc compute ssh "$vm" --zone "$zone" --command 'id jana > /dev/null 2>&1 && test -d /var/lib/jana' > /dev/null 2>&1; do sleep 10; done
  COPYFILE_DISABLE=1 tar -C "$template" -czf "$state/template.tgz" .
  gc compute scp "$state/template.tgz" "$vm:/tmp/template.tgz" --zone "$zone" > /dev/null
  gc compute ssh "$vm" --zone "$zone" --command 'sudo install -d -o jana -g jana -m 0700 /var/lib/jana/template && sudo tar -C /var/lib/jana/template --no-same-owner -xzf /tmp/template.tgz && sudo chown -R jana:jana /var/lib/jana/template && sudo -u jana touch /var/lib/jana/template/.complete && rm /tmp/template.tgz' > /dev/null
fi
echo "address: $address"
echo "host: https://$host"
echo "private links: $state/links.txt"
echo "progress: gcloud --project $project compute ssh $vm --zone $zone --command 'sudo tail -f /var/log/jana-setup.log'"
