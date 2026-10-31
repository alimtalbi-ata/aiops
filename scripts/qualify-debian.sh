#!/usr/bin/env bash
# Read-only Debian qualification. It never starts services or writes to a remote host.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

required=(python3 python3-venv bash node npm curl openssl git)
for cmd in "${required[@]}"; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "BLOCKED|missing_command|$cmd"; exit 2; }
done

echo "PLATFORM=$( . /etc/os-release; printf '%s-%s' "${ID:-unknown}" "${VERSION_ID:-unknown}" )"
python3 --version
node --version
npm --version

VENV="$(mktemp -d "${TMPDIR:-/tmp}/aiops-debian-venv.XXXXXX")"
trap 'rm -rf "$VENV"' EXIT
python3 -m venv "$VENV/venv"
"$VENV/venv/bin/python" -m pip install --disable-pip-version-check --no-warn-script-location -r app/requirements.txt

export PYTHONPATH="$ROOT/app"
"$VENV/venv/bin/python" -m compileall -q app tests tools
bash tests/static-audit.sh

# Focused, deterministic, offline tests for the candidate product slice.
for pattern in \
  "test_policy_safety.py" \
  "test_portal_glpi_operator_view.py" \
  "test_portal_noc_runtime_adapter.py" \
  "test_noc_tenant_scope_fence.py" \
  "test_noc_canonical_correlation.py" \
  "test_acme_impact_read_model.py" \
  "test_acme_san_payments_fixture_contract.py" \
  "test_acme_evidence_utc_preflight.py" \
  "test_cumulative_release_kit_gate.py"; do
  echo "=== UNIT_SUITE=$pattern ==="
  "$VENV/venv/bin/python" -m unittest discover -s tests -p "$pattern" -v
done

node --check app/portal/glpi_operator_view.py 2>/dev/null || true
if [[ -f app/portal/acme_explore_story_client.js ]]; then node --check app/portal/acme_explore_story_client.js; fi
if [[ -f app/portal/portal_bootstrap_client.js ]]; then node --check app/portal/portal_bootstrap_client.js; fi

echo "DEBIAN_READONLY_QUALIFICATION=PASS"
