#!/usr/bin/env bash
# FS.1044 — guarded, authorized portal replacement through its original Docker Compose project.
# Run from the production host only after reviewing the displayed preflight. No DB connector activation.
set -euo pipefail
TARGET=aiops2-rebuild-portal
NEW_IMAGE=aiops2-portal:fs1040-sql-guard-candidate
OLD_IMAGE=aiops2-portal:fs621-explorers-candidate
BACKUP_DIR="${HOME}/aiops2-portal-fs1044-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -m 700 -p "$BACKUP_DIR"
echo "FS1044_BACKUP_DIR=$BACKUP_DIR"
docker image inspect "$NEW_IMAGE" >/dev/null
docker image inspect "$OLD_IMAGE" >/dev/null
docker inspect "$TARGET" > "$BACKUP_DIR/container-inspect.json"
docker inspect "$TARGET" --format '{{.Image}}' > "$BACKUP_DIR/original-image-id.txt"
docker inspect "$TARGET" --format '{{json .NetworkSettings.Networks}}' > "$BACKUP_DIR/networks.json"
docker inspect "$TARGET" --format '{{json .Mounts}}' > "$BACKUP_DIR/mounts.json"
docker inspect "$TARGET" --format '{{json .Config.Env}}' > "$BACKUP_DIR/env.json"
chmod 600 "$BACKUP_DIR"/*
# Read compose metadata from inspect, never print credentials or env values.
mapfile -t META < <(docker inspect "$TARGET" | python3 -c '
import json,sys
d=json.load(sys.stdin)[0]
l=d["Config"].get("Labels") or {}
for k in ("com.docker.compose.project","com.docker.compose.service","com.docker.compose.project.working_dir","com.docker.compose.project.config_files"):
 print(l.get(k,""))
')
PROJECT="${META[0]:-}"; SERVICE="${META[1]:-}"; WORKDIR="${META[2]:-}"; CONFIGS="${META[3]:-}"
if [[ -z "$PROJECT" || -z "$SERVICE" || -z "$WORKDIR" || -z "$CONFIGS" ]]; then
 echo "FS1044_PREFLIGHT=FAIL_NO_COMPOSE_METADATA"; exit 2
fi
[[ -d "$WORKDIR" ]] || { echo "FS1044_PREFLIGHT=FAIL_WORKDIR"; exit 2; }
IFS=, read -r -a FILES <<< "$CONFIGS"
ARGS=()
for f in "${FILES[@]}"; do
 [[ -f "$f" ]] || { [[ -f "$WORKDIR/$f" ]] && f="$WORKDIR/$f" || { echo "FS1044_PREFLIGHT=FAIL_COMPOSE_FILE"; exit 2; }; }
 ARGS+=(-f "$f")
done
# Fail closed if the running image differs from the known base tag.
CURRENT_IMAGE="$(docker inspect "$TARGET" --format '{{.Config.Image}}')"
if [[ "$CURRENT_IMAGE" != "$OLD_IMAGE" ]]; then
 echo "FS1044_PREFLIGHT=FAIL_UNEXPECTED_RUNNING_IMAGE=$CURRENT_IMAGE"; exit 2
fi
echo "FS1044_PROJECT=$PROJECT SERVICE=$SERVICE WORKDIR=$WORKDIR"
echo "FS1044_ORIGINAL_IMAGE=$CURRENT_IMAGE"
echo "FS1044_NEW_IMAGE=$NEW_IMAGE"
# Do not leak compose configuration: inspect only the image chosen for this service.
cd "$WORKDIR"
docker compose -p "$PROJECT" "${ARGS[@]}" config --images >/dev/null
OVERRIDE="$BACKUP_DIR/fs1044-override.yml"
printf 'services:\n  %s:\n    image: %s\n' "$SERVICE" "$NEW_IMAGE" > "$OVERRIDE"
chmod 600 "$OVERRIDE"
# Avoid accidental service dependencies/rebuilds; only replace the target.
echo "FS1044_PREFLIGHT=PASS"
docker compose -p "$PROJECT" "${ARGS[@]}" -f "$OVERRIDE" up -d --no-deps --no-build "$SERVICE"
echo "FS1044_REPLACEMENT_COMMAND=COMPLETED"
docker inspect "$TARGET" --format 'FS1044_RUNNING_IMAGE={{.Config.Image}} STATUS={{.State.Status}}'
if [[ "$(docker inspect "$TARGET" --format '{{.Config.Image}}')" != "$NEW_IMAGE" ]]; then
 echo "FS1044_VERIFY=FAIL_IMAGE"; exit 3
fi
# Local HTTP probe; fail closed if no HTTP 200. Host port 7777 is known from baseline.
for i in 1 2 3 4 5 6 7 8 9 10; do
 if curl --noproxy '*' -fsS --max-time 3 -o /dev/null http://127.0.0.1:7777/health; then
  echo "FS1044_HEALTH=PASS"
  echo "FS1044_DEPLOY=PASS"
  exit 0
 fi
 sleep 2
done
echo "FS1044_HEALTH=FAIL"
echo "FS1044_ROLLBACK_REQUIRED=YES"
echo "FS1044_BACKUP_DIR=$BACKUP_DIR"
exit 4
