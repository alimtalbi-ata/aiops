#!/usr/bin/env bash
set -euo pipefail
echo "FS1071_MODE=READ_ONLY_BROWSER_DIAGNOSTICS"
exec /home/aiops/.local/share/aiops-playwright-venv/bin/python "$(dirname "$0")/fs1071_browser_diagnostics.py"
