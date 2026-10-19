#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cat > "$TMP/default.env" <<'EOF'
AIOPS_DEMO_MODE=0
POSTGRES_PASSWORD=Newaiops26$
AIOPS_ADMIN_TOKEN=Newaiops26$
AIOPS_INTERNAL_TOKEN=Newaiops26$
GLPI_DB_PASSWORD=Newaiops26$
GLPI_DB_ROOT_PASSWORD=Newaiops26$
GRAFANA_ADMIN_PASSWORD=Newaiops26$
N8N_ENCRYPTION_KEY=Newaiops26$-N8N
EOF
if bash "$ROOT/deploy/check-secrets.sh" "$TMP/default.env" >/dev/null 2>&1; then
  echo 'FAIL|default_secrets_accepted'
  exit 1
fi
cat > "$TMP/secure.env" <<'EOF'
AIOPS_DEMO_MODE=0
POSTGRES_PASSWORD=postgres_random_01
AIOPS_ADMIN_TOKEN=shared_internal_random_02
AIOPS_INTERNAL_TOKEN=shared_internal_random_02
GLPI_DB_PASSWORD=glpi_random_03
GLPI_DB_ROOT_PASSWORD=glpi_root_random_04
GRAFANA_ADMIN_PASSWORD=grafana_random_05
N8N_ENCRYPTION_KEY=n8n_random_06
EOF
bash "$ROOT/deploy/check-secrets.sh" "$TMP/secure.env" >/dev/null
sed 's/^AIOPS_INTERNAL_TOKEN=.*/AIOPS_INTERNAL_TOKEN=different_token/' "$TMP/secure.env" > "$TMP/mismatch.env"
if bash "$ROOT/deploy/check-secrets.sh" "$TMP/mismatch.env" >/dev/null 2>&1; then
  echo 'FAIL|mismatched_internal_tokens_accepted'
  exit 1
fi
sed 's/^AIOPS_DEMO_MODE=0$/AIOPS_DEMO_MODE=1/' "$TMP/default.env" > "$TMP/demo.env"
bash "$ROOT/deploy/check-secrets.sh" "$TMP/demo.env" >/dev/null
echo 'SECRET_PREFLIGHT_TEST=PASS'
