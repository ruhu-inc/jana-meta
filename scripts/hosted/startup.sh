#!/usr/bin/env bash
# The VM's startup script. It takes setup-vm.sh from the commit named in the metadata, so the VM runs reviewed code.
set -euo pipefail
commit=$(curl -fsS -H 'Metadata-Flavor: Google' http://metadata.google.internal/computeMetadata/v1/instance/attributes/jana-commit)
curl -fsSL "https://raw.githubusercontent.com/ruhu-inc/jana-meta/$commit/scripts/hosted/setup-vm.sh" -o /run/jana-setup-vm.sh
bash /run/jana-setup-vm.sh
