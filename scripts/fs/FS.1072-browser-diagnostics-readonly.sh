#!/usr/bin/env bash
set -euo pipefail
echo "FS1072_MODE=READ_ONLY_RESILIENT_BROWSER_DIAGNOSTICS"
exec /home/aiops/.local/share/aiops-playwright-venv/bin/python "$(dirname "$0")/fs1072_browser_diagnostics.py"
