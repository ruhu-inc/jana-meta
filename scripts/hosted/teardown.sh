#!/usr/bin/env bash
# Deletes only what deploy.sh created: the demo VM, its disk with all learner data, its address, firewall rule,
# service account and the secret holding the Meta key. Anything else in the project is left alone. It says what really
# happened: a resource already gone is fine, and any other failure is reported, with a failing exit status.
set -uo pipefail
project=${1:?usage: teardown.sh PROJECT_ID}
gc() { gcloud --project "$project" --quiet "$@"; }
failed=0
remove() { # what, the command that shows it exists, the command that deletes it
  local what=$1 show=$2 drop=$3 found
  if ! found=$(eval "gc $show" 2>&1); then
    if grep -qiE "was not found|not_found|does not exist|could not be found" <<<"$found"; then
      echo "already gone: $what"
      return
    fi
    echo "COULD NOT CHECK: $what" >&2
    grep -m1 -E "ERROR|gcloud auth" <<<"$found" >&2
    failed=1
    return
  fi
  if eval "gc $drop" > /dev/null 2>&1; then echo "deleted: $what"; else echo "FAILED TO DELETE: $what" >&2; failed=1; fi
}
account="jana-demo@$project.iam.gserviceaccount.com"
remove "VM and its disk, with all learner data" "compute instances describe jana-demo --zone us-central1-a" "compute instances delete jana-demo --zone us-central1-a --delete-disks all"
remove "web address" "compute addresses describe jana-demo --region us-central1" "compute addresses delete jana-demo --region us-central1"
remove "firewall rule" "compute firewall-rules describe jana-demo-web" "compute firewall-rules delete jana-demo-web"
remove "Meta key secret" "secrets describe jana-meta-api-key" "secrets delete jana-meta-api-key"
remove "service account" "iam service-accounts describe $account" "iam service-accounts delete $account"
if ((failed)); then
  echo "NOT finished: something above still exists and may still be billing. If it says to log in, run: gcloud auth login" >&2
  exit 1
fi
echo "Everything the demo created is gone. The private links in ~/.jana-hosted/$project no longer open anything."
