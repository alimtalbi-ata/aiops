#!/usr/bin/env bash
set -uo pipefail

SRC=/home/aiops/aiops2-v2-delivery
DST=/home/aiops/aiops2-itsm-historical-recovery-20261029
NEW=/home/aiops/aiops2-p0-consolidation

mkdir -p "$DST/tests"

echo "=== RECUPERATION TESTS HISTORIQUES ==="

TESTS=(
  test_acme_hitl_story.py
  test_acme_itsm_binding.py
  test_acme_itsm_correlation.py
  test_glpi_reader_api.py
  test_glpi_real_http.py
  test_glpi_ticket_read.py
  test_hitl_lab.py
  test_hitl_story.py
  test_portal_operator_console.mjs
  test_portal_operator_console.py
  test_portal_operator_read.py
)

for name in "${TESTS[@]}"; do
  path="tests/$name"
  commit=$(git -C "$SRC" log --all -1 --format=%H -- "$path")
  if [ -n "$commit" ] &&
     git -C "$SRC" show "$commit:$path" > "$DST/$path" 2>/dev/null; then
    echo "OK : $name"
  else
    rm -f "$DST/$path"
    echo "ABSENT : $name"
  fi
done

echo
echo "=== DEPENDANCES PORTAL ==="

for name in \
  acme_fixture_contract.py \
  noc_runtime.py \
  noc_correlation.py \
  acme_impact_read_model.py
do
  if [ -f "$NEW/app/portal/$name" ]; then
    echo "PRESENT : $name"
  else
    echo "MANQUANT : $name"
  fi
done

echo
echo "=== DEPENDANCES SHARED ==="

for name in \
  simulation_policy_contract.py \
  glpi_ticket_read.py \
  acme_itsm_binding.py \
  hitl_lab.py
do
  if [ -f "$NEW/app/shared/$name" ]; then
    echo "PRESENT : $name"
  else
    echo "A REINTEGRER : $name"
  fi
done

echo
echo "=== SYNTAXE DES MODULES RECUPERES ==="

python3 - "$DST" <<'PY'
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
failures = []

for path in sorted((root / "app").rglob("*.py")):
    try:
        compile(path.read_bytes(), str(path), "exec")
        print("PASS :", path.relative_to(root))
    except Exception as exc:
        failures.append(str(path))
        print("FAIL :", path, type(exc).__name__)

if failures:
    raise SystemExit(1)

print("SYNTAXE : PASS")
PY

echo
echo "PREFLIGHT TERMINE"
