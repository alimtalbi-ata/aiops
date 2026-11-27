#!/usr/bin/env bash
# Retry only a transient RootlessKit loopback bind collision for one disposable service.
set -euo pipefail

if [[ $# -lt 4 ]]; then
  echo "usage: retry-rootless-compose-port.sh ROOT SERVICE COMPOSE_COMMAND..." >&2
  exit 2
fi
root=$1
service=$2
shift 2
[[ -d "$root" && "$service" =~ ^[a-z0-9][a-z0-9_-]*$ ]] || {
  echo "invalid retry root or service" >&2
  exit 2
}
log=$(mktemp "$root/.${service}-start.XXXXXX")
trap 'rm -f "$log"' EXIT

for attempt in 1 2 3; do
  if "$@" up -d --no-deps "$service" >"$log" 2>&1; then
    cat "$log"
    exit 0
  else
    status=$?
  fi
  cat "$log" >&2
  if [[ "$attempt" == 3 ]] || ! grep -Eqi 'RootlessKit PortManager.AddPort.*address already in use|port is already allocated' "$log"; then
    exit "$status"
  fi
  echo "RootlessKit loopback bind collision; retrying only disposable service $service" >&2
  "$@" rm -sf "$service"
  sleep "$attempt"
done
exit 1
