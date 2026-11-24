#!/usr/bin/env bash
set -Eeuo pipefail
BASE=${BASE_URL:-http://127.0.0.1:${AIOPS_PORTAL_HOST_PORT:-17777}}
ATTEMPTS=${E2E_ATTEMPTS:-90}
[[ "$ATTEMPTS" =~ ^[1-9][0-9]{0,3}$ ]] || exit 2
fail() { echo "SYNTHETIC_E2E=FAIL|$1" >&2; exit 1; }
request() { curl -fsS --connect-timeout 5 --max-time 15 "$@"; }
curl -fsS --connect-timeout 5 --max-time 15 "$BASE/health" >/dev/null || fail health
request "$BASE/api/portal/bootstrap" >/dev/null || fail bootstrap_unavailable
DEMO=$(request -X POST "$BASE/api/demo") || fail demo_unavailable
RUN_ID=$(printf '%s' "$DEMO" | python3 -c 'import json,sys; r=json.load(sys.stdin)["run_id"]; assert isinstance(r,str) and r.strip() and not any(ord(c)<32 for c in r); print(r)') || fail invalid_run_id
for ((i=0; i<ATTEMPTS; i++)); do
  J=$(request "$BASE/api/portal/bootstrap") || fail bootstrap_unavailable
  STATE=$(printf '%s' "$J" | python3 -c 'import json,sys; d=json.load(sys.stdin); rows=d["runs"]["items"]; assert isinstance(rows,list) and all(isinstance(r,dict) for r in rows); matches=[r for r in rows if r.get("run_id")==sys.argv[1]]; assert len(matches)<=1; print(matches[0].get("status","UNKNOWN") if matches else "ABSENT")' "$RUN_ID") || fail invalid_bootstrap
  case "$STATE" in
    RESOLVED) echo "SYNTHETIC_E2E=PASS|run=$RUN_ID"; exit 0 ;;
    FAILED|CANCELLED|BLOCKED) fail terminal_failure ;;
    ABSENT|CREATED|RUNNING|WAITING) ;;
    *) fail unknown_status ;;
  esac
  if ((i+1<ATTEMPTS)); then sleep 1; fi
done
fail timeout
