#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
# Diagnostics in the preflight must be inert shell text; backticks in echo strings
# execute command substitutions and can turn an error path into code execution.
if grep -nF '`' "$ROOT/deploy/check-secrets.sh"; then
  echo 'FAIL|secret_preflight_contains_backtick_command_substitution'
  exit 1
fi
cat > "$TMP/default.env" <<'EOF'
AIOPS_DEMO_MODE=0
POSTGRES_PASSWORD=Newaiops26$
AIOPS_ADMIN_TOKEN=Newaiops26$
AIOPS_INTERNAL_TOKEN=Newaiops26$
AIOPS_PORTAL_READ_TOKEN=Newaiops26$
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
AIOPS_PORTAL_READ_TOKEN=portal_read_random_07
GLPI_DB_PASSWORD=glpi_random_03
GLPI_DB_ROOT_PASSWORD=glpi_root_random_04
GRAFANA_ADMIN_PASSWORD=grafana_random_05
N8N_ENCRYPTION_KEY=n8n_random_06
EOF
bash "$ROOT/deploy/check-secrets.sh" "$TMP/secure.env" >/dev/null
# Optional signed NOC bridge must be all-or-none and use a matching explicit origin.
cp "$TMP/secure.env" "$TMP/noc-partial.env"
printf '%s\n' 'AIOPS_NOC_READ_MODEL_URL=https://noc.example.test/api/read-model' >> "$TMP/noc-partial.env"
if bash "$ROOT/deploy/check-secrets.sh" "$TMP/noc-partial.env" >/dev/null 2>&1; then
  echo 'FAIL|partial_noc_source_configuration_accepted'
  exit 1
fi
cp "$TMP/secure.env" "$TMP/noc-secure.env"
cat >> "$TMP/noc-secure.env" <<'EOF'
AIOPS_NOC_READ_MODEL_URL=https://noc.example.test/api/read-model
AIOPS_NOC_READ_MODEL_TOKEN=upstream_token_random_1234567890
AIOPS_NOC_READ_MODEL_HMAC_KEY=hmac_key_random_012345678901234567890123456789
AIOPS_NOC_ALLOWED_ORIGINS=https://noc.example.test
EOF
bash "$ROOT/deploy/check-secrets.sh" "$TMP/noc-secure.env" >/dev/null
sed 's|^AIOPS_NOC_ALLOWED_ORIGINS=.*|AIOPS_NOC_ALLOWED_ORIGINS=https://other.example.test|' "$TMP/noc-secure.env" > "$TMP/noc-origin-mismatch.env"
if bash "$ROOT/deploy/check-secrets.sh" "$TMP/noc-origin-mismatch.env" >/dev/null 2>&1; then
  echo 'FAIL|noc_origin_mismatch_accepted'
  exit 1
fi
sed 's|^AIOPS_NOC_READ_MODEL_HMAC_KEY=.*|AIOPS_NOC_READ_MODEL_HMAC_KEY=short|' "$TMP/noc-secure.env" > "$TMP/noc-short-hmac.env"
if bash "$ROOT/deploy/check-secrets.sh" "$TMP/noc-short-hmac.env" >/dev/null 2>&1; then
  echo 'FAIL|short_noc_hmac_key_accepted'
  exit 1
fi
sed 's/^AIOPS_INTERNAL_TOKEN=.*/AIOPS_INTERNAL_TOKEN=different_token/' "$TMP/secure.env" > "$TMP/mismatch.env"
if bash "$ROOT/deploy/check-secrets.sh" "$TMP/mismatch.env" >/dev/null 2>&1; then
  echo 'FAIL|mismatched_internal_tokens_accepted'
  exit 1
fi
sed 's/^AIOPS_DEMO_MODE=0$/AIOPS_DEMO_MODE=1/' "$TMP/default.env" > "$TMP/demo.env"
bash "$ROOT/deploy/check-secrets.sh" "$TMP/demo.env" >/dev/null
sed 's/^AIOPS_DEMO_MODE=0$/AIOPS_DEMO_MODE=1/; s/^AIOPS_INTERNAL_TOKEN=.*/AIOPS_INTERNAL_TOKEN=different_token/' "$TMP/secure.env" > "$TMP/demo-mismatch.env"
if bash "$ROOT/deploy/check-secrets.sh" "$TMP/demo-mismatch.env" >/dev/null 2>&1; then
  echo 'FAIL|demo_token_mismatch_accepted'
  exit 1
fi
mkdir -p "$TMP/init/config" "$TMP/init/deploy"
cp "$ROOT/config/.env.example" "$TMP/init/config/.env.example"
cp "$ROOT/deploy/init-env.sh" "$TMP/init/deploy/init-env.sh"
bash "$TMP/init/deploy/init-env.sh" >/dev/null
bash "$ROOT/deploy/check-secrets.sh" "$TMP/init/.env" >/dev/null
[[ "$(stat -c '%a' "$TMP/init/.env")" == "600" ]]
ADMIN_TOKEN="$(sed -n 's/^AIOPS_ADMIN_TOKEN=//p' "$TMP/init/.env")"
INTERNAL_TOKEN="$(sed -n 's/^AIOPS_INTERNAL_TOKEN=//p' "$TMP/init/.env")"
[[ -n "$ADMIN_TOKEN" && "$ADMIN_TOKEN" == "$INTERNAL_TOKEN" ]]
PORTAL_READ_TOKEN="$(sed -n 's/^AIOPS_PORTAL_READ_TOKEN=//p' "$TMP/init/.env")"
[[ -n "$PORTAL_READ_TOKEN" && "$PORTAL_READ_TOKEN" != "$INTERNAL_TOKEN" ]]
BEFORE="$(sha256sum "$TMP/init/.env" | cut -d' ' -f1)"
bash "$TMP/init/deploy/init-env.sh" >/dev/null
AFTER="$(sha256sum "$TMP/init/.env" | cut -d' ' -f1)"
[[ "$BEFORE" == "$AFTER" ]]
# Existing environment migration must repair only known bad defaults and preserve secrets.
mkdir -p "$TMP/upgrade/config" "$TMP/upgrade/deploy"
cp "$ROOT/config/.env.example" "$TMP/upgrade/config/.env.example"
cp "$ROOT/deploy/init-env.sh" "$TMP/upgrade/deploy/init-env.sh"
cp "$TMP/init/.env" "$TMP/upgrade/.env"
sed -i 's|^TEMPORAL_IMAGE=.*|TEMPORAL_IMAGE=temporalio/auto-setup:1.32.1|' "$TMP/upgrade/.env"
sed -i 's|^TEMPORAL_UI_IMAGE=.*|TEMPORAL_UI_IMAGE=temporalio/ui:2.56.0|' "$TMP/upgrade/.env"
sed -i '/^TEMPORAL_ADMINTOOLS_IMAGE=/d' "$TMP/upgrade/.env"
BEFORE_TOKEN="$(sed -n 's/^AIOPS_INTERNAL_TOKEN=//p' "$TMP/upgrade/.env")"
BEFORE_PORTAL_READ_TOKEN="$(sed -n 's/^AIOPS_PORTAL_READ_TOKEN=//p' "$TMP/upgrade/.env")"
bash "$TMP/upgrade/deploy/init-env.sh" >/dev/null
grep -Fxq 'TEMPORAL_IMAGE=temporalio/server:1.31.0' "$TMP/upgrade/.env"
grep -Fxq 'TEMPORAL_ADMINTOOLS_IMAGE=temporalio/admin-tools:1.31.0' "$TMP/upgrade/.env"
grep -Fxq 'TEMPORAL_UI_IMAGE=temporalio/ui:2.49.1' "$TMP/upgrade/.env"
[[ "$(sed -n 's/^AIOPS_INTERNAL_TOKEN=//p' "$TMP/upgrade/.env")" == "$BEFORE_TOKEN" ]]
[[ "$(sed -n 's/^AIOPS_PORTAL_READ_TOKEN=//p' "$TMP/upgrade/.env")" == "$BEFORE_PORTAL_READ_TOKEN" ]]
[[ "$(stat -c '%a' "$TMP/upgrade/.env")" == "600" ]]
# Legacy .env without the new portal read credential must migrate fail-closed.
mkdir -p "$TMP/legacy/config" "$TMP/legacy/deploy"
cp "$ROOT/config/.env.example" "$TMP/legacy/config/.env.example"
cp "$ROOT/deploy/init-env.sh" "$TMP/legacy/deploy/init-env.sh"
cp "$TMP/init/.env" "$TMP/legacy/.env"
sed -i '/^AIOPS_PORTAL_READ_TOKEN=/d' "$TMP/legacy/.env"
bash "$TMP/legacy/deploy/init-env.sh" >/dev/null
LEGACY_PORTAL_READ_TOKEN="$(sed -n 's/^AIOPS_PORTAL_READ_TOKEN=//p' "$TMP/legacy/.env")"
[[ -n "$LEGACY_PORTAL_READ_TOKEN" && "$LEGACY_PORTAL_READ_TOKEN" != "$INTERNAL_TOKEN" ]]
[[ "$(stat -c '%a' "$TMP/legacy/.env")" == "600" ]]
echo 'SECRET_PREFLIGHT_TEST=PASS'
