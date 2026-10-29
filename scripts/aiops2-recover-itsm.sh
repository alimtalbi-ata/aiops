#!/usr/bin/env bash
set -uo pipefail

SRC=/home/aiops/aiops2-v2-delivery
DST=/home/aiops/aiops2-itsm-historical-recovery-20261029

mkdir -p "$DST"

FILES=(
  app/glpi_reader/main.py
  app/glpi_reader/Dockerfile
  app/shared/glpi_ticket_read.py
  app/shared/acme_itsm_binding.py
  app/shared/hitl_lab.py
  app/portal/acme_itsm_correlation.py
  app/portal/operator_console.py
  app/portal/operator_console.js
  app/portal/acme_hitl_story.py
  app/portal/hitl_demo_read_model.py
)

echo "=== RECUPERATION HISTORIQUE ==="

for file in "${FILES[@]}"; do
  commit=$(git -C "$SRC" log --all -1 \
    --format=%H -- "$file")

  if [ -z "$commit" ]; then
    echo "ABSENT : $file"
    continue
  fi

  mkdir -p "$DST/$(dirname "$file")"

  if git -C "$SRC" show "$commit:$file" \
      > "$DST/$file" 2>/dev/null; then
    echo "RECUPERE : $file @ ${commit:0:12}"
  else
    rm -f "$DST/$file"
    echo "ECHEC : $file"
  fi
done

echo
echo "=== CONTENU RECUPERE ==="
find "$DST" -type f -printf '%P\n' | sort

echo
echo "=== POINTS D'INTEGRATION ==="
grep -RnE \
  '^(@app\.|def |async def |class )|/api/|/apirest\.php|initSession' \
  "$DST/app" \
  --include='*.py' \
  | head -110

echo
echo "=== RESULTAT ==="
echo "DOSSIER : $DST"
echo "AUCUN CONTENEUR MODIFIE"
echo "AUCUN FICHIER DU DEPOT ACTIF MODIFIE"
