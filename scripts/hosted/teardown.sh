#!/usr/bin/env bash
# Deletes only what deploy.sh created: the demo VM, its disk with all learner data, its address, firewall rule,
# service account and the secret holding the Meta key. Anything else in the project is left alone.
set -euo pipefail
project=${1:?usage: teardown.sh PROJECT_ID}
gc() { gcloud --project "$project" --quiet "$@"; }
gc compute instances delete jana-demo --zone us-central1-a --delete-disks all || true
gc compute addresses delete jana-demo --region us-central1 || true
gc compute firewall-rules delete jana-demo-web || true
gc secrets delete jana-meta-api-key || true
gc iam service-accounts delete "jana-demo@$project.iam.gserviceaccount.com" || true
echo "Deleted. The private links in ~/.jana-hosted/$project no longer open anything."
