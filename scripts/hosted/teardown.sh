#!/usr/bin/env bash
# Deletes the hosted demo, its disk with all learner data, its address and its firewall rule. The Meta key secret goes too.
set -euo pipefail
project=${1:?usage: teardown.sh PROJECT_ID}
gc() { gcloud --project "$project" --quiet "$@"; }
gc compute instances delete jana-demo --zone us-central1-a --delete-disks all || true
gc compute addresses delete jana-demo --region us-central1 || true
gc compute firewall-rules delete jana-demo-web || true
gc secrets delete jana-meta-api-key || true
echo "Deleted. The private links in ~/.jana-hosted/$project no longer open anything."
