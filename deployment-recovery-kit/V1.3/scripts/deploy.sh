#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
APPLY=0; COMPOSE=""
while (($#)); do
  case "$1" in
    --compose) [[ $# -ge 2 ]] || { echo "--compose requires a path" >&2; exit 2; }; COMPOSE="$2"; shift 2 ;;
    --apply) APPLY=1; shift ;;
    -h|--help) echo "Usage: $0 --compose /absolute/path/compose.yml [--apply]"; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done
[[ -n "$COMPOSE" && -f "$COMPOSE" ]] || { echo "BLOCKED: provide a real, audited Compose file; this kit does not fabricate the missing V2 compose.yml." >&2; exit 10; }
docker compose -f "$COMPOSE" config --quiet
echo COMPOSE_CONFIG=PASS
if (( APPLY == 0 )); then echo MODE=DRY_RUN; echo NO_CONTAINERS_CHANGED=YES; exit 0; fi
read -r -p "Type APPLY-AIOPS2 to continue: " answer
[[ "$answer" == APPLY-AIOPS2 ]] || { echo CANCELLED; exit 20; }
docker compose -f "$COMPOSE" up -d
echo COMPOSE_UP=ISSUED
