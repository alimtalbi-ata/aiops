#!/usr/bin/env bash
set -uo pipefail

SRC=/home/aiops/aiops2-v2-delivery
DST=/home/aiops/aiops2-itsm-historical-recovery-20261029
NEW=/home/aiops/aiops2-p0-consolidation

FILES=(
  app/portal/acme_fixture_contract.py
  app/portal/noc_runtime.py
  app/portal/noc_correlation.py
  app/portal/acme_impact_read_model.py
  app/shared/simulation_policy_contract.py
)

echo "=== RECUPERATION DEPENDANCES ==="

for file in "${FILES[@]}"; do
  mkdir -p "$DST/$(dirname "$file")"

  commit=$(git -C "$SRC" log --all -1 --format=%H -- "$file")

  if [ -n "$commit" ] &&
     git -C "$SRC" show "$commit:$file" \
       > "$DST/$file" 2>/dev/null; then
    echo "OK : $file @ ${commit:0:12}"
  else
    rm -f "$DST/$file"
    echo "ABSENT : $file"
  fi
done

echo
echo "=== COMPILATION COMPLETE ==="

python3 - "$DST" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
failures = []

for file in sorted((root / "app").rglob("*.py")):
    try:
        compile(file.read_bytes(), str(file), "exec")
        print("PASS", file.relative_to(root))
    except Exception as exc:
        failures.append(str(file))
        print("FAIL", file, type(exc).__name__)

if failures:
    raise SystemExit(1)

print("COMPILATION COMPLETE : PASS")
PY

echo
echo "=== TESTS DISPONIBLES ==="

for python in python3 "$NEW/.venv/bin/python"; do
  if [ "$python" = python3 ] || [ -x "$python" ]; then
    "$python" -m pytest --version 2>&1 || true
  fi
done

echo
echo "=== DEPENDANCES SUPPLEMENTAIRES ==="

grep -RhE '^from (portal|shared)\.|^import (portal|shared)' \
  "$DST/app" --include='*.py' 2>/dev/null \
  | sort -u

echo
echo "=== ETAT DES SERVICES ==="

for service in core worker portal copilot glpi n8n; do
  docker inspect \
    --format '{{.Name}} : {{.State.Status}}' \
    "aiops2-rebuild-$service" 2>/dev/null || true
done

echo
echo "RECUPERATION COMPLETE — AUCUN SERVICE MODIFIE"
