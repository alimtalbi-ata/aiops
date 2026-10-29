#!/usr/bin/env bash
set -uo pipefail

SRC=/home/aiops/aiops2-v2-delivery
DST=/home/aiops/aiops2-itsm-historical-recovery-20261029
NEW=/home/aiops/aiops2-p0-consolidation

echo "=== DEPENDANCE TENANT SCOPE ==="

file=app/shared/tenant_scope.py

if [ -f "$NEW/$file" ]; then
  echo "PRESENT DANS LE DEPOT ACTUEL"
elif [ -f "$DST/$file" ]; then
  echo "DEJA RECUPERE"
else
  commit=$(git -C "$SRC" log --all -1 --format=%H -- "$file")
  if [ -n "$commit" ]; then
    mkdir -p "$DST/app/shared"
    if git -C "$SRC" show "$commit:$file" > "$DST/$file"; then
      echo "RECUPERE : $file"
    else
      echo "ECHEC : $file"
    fi
  else
    echo "MANQUANT : $file"
  fi
fi

echo
echo "=== ROUTES HISTORIQUES ET ACTUELLES ==="

python3 - "$DST" "$NEW" <<'PY'
import ast
import pathlib
import sys

for label, root in [
    ("HISTORIQUE", pathlib.Path(sys.argv[1])),
    ("ACTUEL", pathlib.Path(sys.argv[2])),
]:
    print("---", label, "---")
    portal = root / "app/portal"
    for path in sorted(portal.glob("*.py")):
        try:
            tree = ast.parse(path.read_text())
        except Exception:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                func = decorator.func
                if not isinstance(func, ast.Attribute):
                    continue
                if func.attr not in ("get", "post", "put", "delete"):
                    continue
                if not decorator.args:
                    continue
                route = decorator.args[0]
                if isinstance(route, ast.Constant) and isinstance(route.value, str):
                    print(func.attr.upper(), route.value, path.name)
PY

echo
echo "=== ENVIRONNEMENT TEST PORTAL ==="

docker exec aiops2-rebuild-portal python - <<'PY'
import importlib.util

for module in ("pytest", "fastapi", "httpx", "requests"):
    print(module, ":", bool(importlib.util.find_spec(module)))
PY

echo
echo "=== TESTS HISTORIQUES : INVENTAIRE ==="

find "$DST/tests" -maxdepth 1 -type f \
  -printf '%f\n' | sort

echo
echo "=== GLPI READER : CONFIGURATION REQUISE ==="

grep -nE \
  'AIOPS_GLPI_|GLPIUnverified|HTTPException|@app\.' \
  "$DST/app/glpi_reader/main.py" \
  "$DST/app/shared/glpi_ticket_read.py" \
  | head -65

echo
echo "=== ETAT FINAL ==="

for service in core worker portal glpi; do
  docker inspect \
    --format '{{.Name}} : {{.State.Status}}' \
    "aiops2-rebuild-$service"
done

echo "QUALIFICATION STATIQUE TERMINEE"
