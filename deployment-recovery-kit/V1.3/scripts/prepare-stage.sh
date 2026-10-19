#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
if [[ "${1:-}" != "--prepare" ]]; then
  echo "DRY RUN. Rerun with --prepare to create copies; original sources remain unchanged."
  exit 0
fi
V69=/home/aiops/exports/AIOPS-R33-LOGICAL-20261007-112249/03-SOURCES/V69/stack
TEMPORAL=/home/aiops/.temporal-stage-20261017-171712
DEST=/home/aiops/aiops2-reconstruction/staging
for src in "$V69" "$TEMPORAL"; do [[ -d "$src" ]] || { echo "REQUIRED_SOURCE_MISSING=$src" >&2; exit 2; }; done
mkdir -p "$DEST"; chmod 700 "$DEST"
for pair in "v69-source:$V69" "temporal-stage:$TEMPORAL"; do
  name="${pair%%:*}"; src="${pair#*:}"; target="$DEST/$name"
  [[ ! -e "$target" ]] || { echo "REFUSING_TO_OVERWRITE=$target" >&2; exit 3; }
  mkdir -p "$target"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --exclude='.git' --exclude='.venv' --exclude='__pycache__' --exclude='node_modules' --exclude='backups' --exclude='docker-data' "$src/" "$target/"
  else cp -a "$src/." "$target/"; fi
  (cd "$target" && find . -type f -print0 | sort -z | xargs -0 -r sha256sum) > "$DEST/$name.SHA256SUMS"
  echo "STAGED=$target"
done
echo STAGING_COMPLETE=YES; echo DEPLOYMENT_PERFORMED=NO
