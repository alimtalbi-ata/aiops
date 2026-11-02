#!/usr/bin/env bash
# Existing poll.sh invokes this only on a new stable SHA. P0 is read-only.
set -Eeuo pipefail
umask 077
delivery="$(cd "$(dirname "$0")/.." && pwd)"
exec /usr/bin/python3 "$delivery/deploy/debian-portal-preflight.py"
