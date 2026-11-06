#!/usr/bin/env bash
set -euo pipefail
echo "FS1070_MODE=EXISTING_PLAYWRIGHT_READONLY_SNAPSHOTS"
VENV=/home/aiops/.local/share/aiops-playwright-venv/bin/python
test -x "$VENV"
test -x /usr/bin/chromium
exec "$VENV" "$(dirname "$0")/fs1070_browser_snapshots.py"
