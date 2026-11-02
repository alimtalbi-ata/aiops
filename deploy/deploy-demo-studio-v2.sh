#!/usr/bin/env bash
# Called by installed Debian poll.sh once per new stable SHA.
set -Eeuo pipefail
umask 077
delivery="$(cd "$(dirname "$0")/.." && pwd)"
status=0
bash "$delivery/deploy/debian-portal-deploy.sh" || status=$?
/usr/bin/python3 "$delivery/deploy/debian-poller-qualification.py" || true
exit "$status"
