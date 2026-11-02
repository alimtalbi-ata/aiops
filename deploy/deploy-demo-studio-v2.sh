#!/usr/bin/env bash
# Installed poll.sh calls this after a new stable SHA. No legacy Docker replacement.
set -Eeuo pipefail
umask 077
delivery="$(cd "$(dirname "$0")/.." && pwd)"
exec /usr/bin/python3 "$delivery/deploy/debian-poller-qualification.py"
