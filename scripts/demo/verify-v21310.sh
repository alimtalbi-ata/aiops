#!/usr/bin/env bash
# Read-only validation of the single portal. No credentials, ports or container mutations.
set -u
host="${1:-http://10.79.94.202:17777}"
for path in /health / /demo-studio /demo/ /demo/star; do
  status=$(curl -sS --max-time 6 -o /dev/null -w '%{http_code}' "${host}${path}" 2>/dev/null) || status=000
  printf '%-20s %s\n' "$path" "$status"
done
echo 'Expected before V21310 deployment: /demo/ 403. After an approved deployment: /demo/ and /demo/star 200.'
echo 'Do not enable historical replays or HTTP Basic over cleartext HTTP.'
