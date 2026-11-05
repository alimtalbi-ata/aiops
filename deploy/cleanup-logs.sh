#!/bin/sh
set -eu
[ "$#" -eq 1 ] || { echo "usage: $0 RUN_ID" >&2; exit 2; }
exec python3 "$(dirname "$0")/fs_demo.py" cleanup-logs --run-id "$1" --approval SYNTHETIC_APPROVED
