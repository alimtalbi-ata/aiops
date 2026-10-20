#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/deploy" "$TMP/config"
cp "$ROOT/deploy/init-env.sh" "$ROOT/deploy/install-isolated.sh" "$TMP/deploy/"
cp "$ROOT/config/.env.example" "$TMP/config/"
(
 cd "$TMP"
 bash deploy/install-isolated.sh --configure-only >/dev/null
 grep -Fxq 'AIOPS_STACK_ID=aiops2-rebuild' .env
 grep -Fxq 'COMPOSE_PROJECT_NAME=aiops2-rebuild' .env
 grep -Fxq 'AIOPS_BIND_IP=127.0.0.1' .env
 grep -Fxq 'AIOPS_PORTAL_HOST_PORT=17777' .env
 [[ "$(stat -c '%a' .env)" == 600 ]]
 [[ "$(wc -l < .env)" -gt 20 ]]
)
# Compose rendering is validated without creating any container.
env -u COMPOSE_PROJECT_NAME -u AIOPS_STACK_ID docker compose -f "$ROOT/compose.yml" --env-file "$TMP/.env" -p aiops2-rebuild config --format json > "$TMP/isolated.json"
python3 - "$TMP/isolated.json" <<'PY'
import json,sys
data=json.load(open(sys.argv[1],encoding="utf-8"))
prefix="aiops2-rebuild"
assert data["name"]==prefix, "project name not isolated"
for service_name,service in data["services"].items():
    if "container_name" in service:
        assert service["container_name"].startswith(prefix+"-"), service_name
for net in data["networks"].values():
    assert net["name"].startswith(prefix+"-"), net
for volume in data["volumes"].values():
    assert volume["name"].startswith(prefix+"-"), volume
portal=data["services"]["aiops2-portal"]
published=portal["ports"][0]
assert int(published["published"])==17777, published
assert published["host_ip"]=="127.0.0.1", published
print("ISOLATED_COMPOSE_CONTRACT=PASS|containers="+str(len(data["services"])))
PY
