#!/usr/bin/env bash
set -uo pipefail

SRC=/home/aiops/aiops2-v2-delivery
OLD=/home/aiops/aiops2-itsm-historical-recovery-20261029
NEW=/home/aiops/aiops2-p0-consolidation
CAND=/home/aiops/aiops2-itsm-portal-candidate-20261029
IMAGE=aiops2-itsm-qualification:20261029

echo "=== PREPARATION CANDIDAT ==="

if [ -e "$CAND" ]; then
  echo "ARRET : dossier candidat deja existant : $CAND"
  exit 1
fi

mkdir -p "$CAND"
cp -a "$NEW/app" "$CAND/app"
mkdir -p "$CAND/tests"

cp -a "$OLD/tests/." "$CAND/tests/"
cp -a "$OLD/app/portal/." "$CAND/app/portal/"
cp -a "$OLD/app/shared/." "$CAND/app/shared/"
cp -a "$OLD/app/policy" "$CAND/app/"
cp -a "$OLD/demo" "$CAND/"

# Restaurer le point d'entree Portal ACTUEL, non celui de l'historique.
cp "$NEW/app/portal/main.py" "$CAND/app/portal/main.py"

echo
echo "=== COMPLEMENTS HISTORIQUES ==="

FILES=(
  app/portal/acme_explore_story.py
  app/portal/acme_hitl_story.py
  app/portal/operator_read.py
)

for file in "${FILES[@]}"; do
  if [ -f "$CAND/$file" ]; then
    echo "PRESENT : $file"
    continue
  fi

  commit=$(git -C "$SRC" log --all -1 --format=%H -- "$file")
  if [ -z "$commit" ] ||
     ! git -C "$SRC" show "$commit:$file" > "$CAND/$file"; then
    echo "MANQUANT : $file"
    exit 1
  fi
  echo "RECUPERE : $file"
done

echo
echo "=== RACCORDEMENT DES ROUTES DANS LE CANDIDAT ==="

python3 - "$CAND/app/portal/main.py" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
source = path.read_text()

marker = "# AIOPS2_HISTORICAL_CANDIDATE_ROUTES"

if marker in source:
    raise SystemExit("Candidat deja modifie")

addition = '''
# AIOPS2_HISTORICAL_CANDIDATE_ROUTES
from portal import (
    operator_console,
    operator_read,
    acme_itsm_correlation,
    acme_explore_story,
)

app.include_router(operator_console.router)
app.include_router(operator_read.router)
app.include_router(acme_itsm_correlation.router)
app.include_router(acme_explore_story.router)
'''

path.write_text(source + "\n" + addition)
print("RACCORDEMENT CANDIDAT : OK")
PY

echo
echo "=== TESTS CANDIDAT ISOLE ==="

docker run --rm \
  --network none \
  --read-only \
  --tmpfs /tmp:rw,nosuid,size=128m \
  -e PYTHONPATH=/candidate:/candidate/app \
  -e PYTHONDONTWRITEBYTECODE=1 \
  -v "$CAND:/candidate:ro" \
  --entrypoint python \
  "$IMAGE" \
  -m pytest -q --tb=short -p no:cacheprovider \
  /candidate/tests/test_acme_itsm_binding.py \
  /candidate/tests/test_acme_itsm_correlation.py \
  /candidate/tests/test_glpi_ticket_read.py \
  /candidate/tests/test_glpi_reader_api.py \
  /candidate/tests/test_hitl_lab.py \
  /candidate/tests/test_hitl_story.py \
  /candidate/tests/test_acme_hitl_story.py \
  /candidate/tests/test_portal_operator_console.py \
  /candidate/tests/test_portal_operator_read.py

RESULT=$?

echo
echo "=== RESULTAT CANDIDAT : $RESULT ==="
echo "DOSSIER : $CAND"
echo "AUCUN DEPLOIEMENT EFFECTUE"

exit "$RESULT"
