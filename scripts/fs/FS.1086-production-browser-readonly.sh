#!/usr/bin/env bash
set -euo pipefail
echo "FS1086_MODE=READ_ONLY_PRODUCTION_BROWSER_AUDIT"
docker inspect aiops2-rebuild-portal --format 'FS1086_IMAGE={{.Config.Image}}'
if [[ "$(docker inspect aiops2-rebuild-portal --format '{{.Config.Image}}')" != "aiops2-portal:fs1073-csp-candidate" ]]; then
 echo "FS1086_UNEXPECTED_IMAGE";exit 1
fi
/home/aiops/.local/share/aiops-playwright-venv/bin/python "$(dirname "$0")/fs1086_prod_browser_audit.py"
echo "FS1086_PRODUCTION_MUTATION=NONE"
