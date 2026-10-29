#!/usr/bin/env bash
set -uo pipefail

OLD=/home/aiops/aiops2-itsm-historical-recovery-20261029
NEW=/home/aiops/aiops2-p0-consolidation

echo "=== IMPORTS ET DEPENDANCES ==="

python3 - "$OLD" <<'PY'
import ast
import pathlib
import sys

root = pathlib.Path(sys.argv[1])

for path in sorted((root / "app").rglob("*.py")):
    print("\n---", path.relative_to(root), "---")
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                print("IMPORT", item.name)
        elif isinstance(node, ast.ImportFrom):
            print("FROM", node.module, "IMPORT",
                  ",".join(n.name for n in node.names))
PY

echo
echo "=== ROUTES HISTORIQUES ==="
grep -RnE \
  '@(app|router)\.(get|post|put|delete)|include_router|APIRouter' \
  "$OLD/app" --include='*.py' | head -100

echo
echo "=== ROUTES ET IMPORTS PORTAL ACTUEL ==="
grep -nE \
  'include_router|APIRouter|operator|hitl|correlation|glpi|@app.get' \
  "$NEW/app/portal/main.py" | head -100

echo
echo "=== DEPENDANCES GLPI ==="
sed -n '1,115p' "$OLD/app/glpi_reader/main.py"
sed -n '50,90p' "$OLD/app/shared/glpi_ticket_read.py"

echo
echo "=== CONSOLE HISTORIQUE ==="
sed -n '1,105p' "$OLD/app/portal/operator_console.py"

echo
echo "=== TESTS HISTORIQUES ASSOCIES ==="
git -C /home/aiops/aiops2-v2-delivery \
  log --all --name-only --format= \
  | sort -u \
  | grep -Ei '^tests/.*(glpi|itsm|hitl|operator)' \
  | head -65

echo
echo "AUDIT TERMINE — AUCUN DEPLOIEMENT"
