#!/usr/bin/env bash
set -Eeuo pipefail
BASE="${BASE_URL:-http://127.0.0.1:7777}"
ENV_FILE="${ENV_FILE:-.env}"
[[ -f "$ENV_FILE" ]] || { echo "FAIL|env_file_missing|$ENV_FILE"; exit 1; }
OPERATOR_TOKEN="$(sed -n 's/^AIOPS_PORTAL_OPERATOR_TOKEN=//p' "$ENV_FILE" | tail -n 1)"
[[ -n "$OPERATOR_TOKEN" ]] || { echo 'FAIL|operator_token_missing'; exit 1; }
AUTH=(-H "Authorization: Bearer $OPERATOR_TOKEN")
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

curl -fsS "$BASE/health" >/dev/null
STATUS="$(curl -sS -o "$TMP_DIR/unauth.json" -w '%{http_code}' "$BASE/api/portal/bootstrap")"
[[ "$STATUS" == "401" ]] || { echo "FAIL|bootstrap_without_auth|http=$STATUS"; exit 1; }
STATUS="$(curl -sS -o "$TMP_DIR/demo-unauth.json" -w '%{http_code}' -X POST "$BASE/api/demo")"
[[ "$STATUS" == "401" ]] || { echo "FAIL|demo_without_auth|http=$STATUS"; exit 1; }

curl -fsS "${AUTH[@]}" "$BASE/api/portal/bootstrap" >"$TMP_DIR/bootstrap.json"
curl -fsS -X POST "${AUTH[@]}" "$BASE/api/demo" >"$TMP_DIR/demo.json"
RUN_ID="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("run_id",""))' "$TMP_DIR/demo.json")"
[[ -n "$RUN_ID" ]] || { echo 'FAIL|demo_run_id_missing'; cat "$TMP_DIR/demo.json"; exit 1; }

FOUND=0
for _ in $(seq 1 90); do
  if curl -fsS "${AUTH[@]}" "$BASE/api/portal/bootstrap" >"$TMP_DIR/current.json" && grep -q "$RUN_ID" "$TMP_DIR/current.json"; then FOUND=1; break; fi
  sleep 1
done
[[ "$FOUND" == "1" ]] || { echo "FAIL|run_not_visible|run=$RUN_ID"; exit 1; }
echo "SYNTHETIC_E2E=PASS|run=$RUN_ID|auth=PASS|unauthenticated_mutations=BLOCKED"
