#!/usr/bin/env bash
# Consistent logical backup plus labelled volume snapshots for ONE verified Compose project.
# Backups contain database records and secrets. Never publish them to GitHub or chat.
set -Eeuo pipefail
umask 077
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[[ -f .env ]] || { echo 'FAIL|missing_env'; exit 2; }
STACK_ID="$(sed -n 's/^AIOPS_STACK_ID=//p' .env | head -1)"
STACK_ID="${STACK_ID:-aiops2}"
[[ "$STACK_ID" =~ ^[a-z][a-z0-9-]{2,28}$ ]] || { echo 'FAIL|invalid_stack_id'; exit 2; }
PROJECT="$(docker compose --env-file .env config --format json | python3 -c 'import json,sys;print(json.load(sys.stdin)["name"])')"
[[ "$PROJECT" == "$STACK_ID" ]] || { echo "FAIL|stack_identity_mismatch|expected=$STACK_ID|actual=$PROJECT"; exit 3; }
DB_CONTAINER="$(docker compose --env-file .env ps -q aiops2-postgres)"
[[ -n "$DB_CONTAINER" ]] || { echo 'FAIL|postgres_container_not_running'; exit 3; }
OWNER="$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "$DB_CONTAINER")"
[[ "$OWNER" == "$STACK_ID" ]] || { echo 'FAIL|postgres_owned_by_another_stack'; exit 3; }
ARCHIVE_IMAGE="$(docker inspect --format '{{.Config.Image}}' "$DB_CONTAINER")"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${1:-$ROOT/backups/$STACK_ID-$STAMP}"
[[ "$OUT" != "$ROOT" && "$OUT" != / ]] || { echo 'FAIL|unsafe_backup_directory'; exit 3; }
mkdir -p "$(dirname "$OUT")"
mkdir -m 700 "$OUT" || { echo 'FAIL|backup_destination_exists_or_is_not_writable'; exit 3; }
OUT="$(cd "$OUT" && pwd)"
printf 'INCOMPLETE|stack_id=%s\n' "$STACK_ID" > "$OUT/.BACKUP_INCOMPLETE"
echo "BACKUP_BEGIN|stack_id=$STACK_ID|destination=$OUT"

# Logical database captures. The Temporal visibility database is not optional.
docker compose --env-file .env exec -T aiops2-postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' > "$OUT/aiops.dump"
docker compose --env-file .env exec -T aiops2-postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d n8n --format=custom' > "$OUT/n8n.dump"
docker compose --env-file .env exec -T aiops2-temporal-postgres pg_dump -U temporal -d temporal --format=custom > "$OUT/temporal.dump"
docker compose --env-file .env exec -T aiops2-temporal-postgres pg_dump -U temporal -d temporal_visibility --format=custom > "$OUT/temporal_visibility.dump"
docker compose --env-file .env exec -T aiops2-glpi-db sh -c 'mariadb-dump -uroot -p"$MARIADB_ROOT_PASSWORD" --single-transaction --routines --events --all-databases' > "$OUT/glpi-mariadb.sql"

# Source volumes belong to the selected AIOps stack, not whichever volume
# an older legacy application happens to use.
for suffix in n8n-data glpi-data grafana-data prometheus-data; do
  volume="$STACK_ID-$suffix"
  logical="aiops2-$suffix"
  actual="$(docker volume inspect --format '{{.Name}}' "$volume" 2>/dev/null)" || {
    echo "FAIL|stack_volume_missing|$volume"; exit 4;
  }
  [[ "$actual" == "$volume" ]] || { echo "FAIL|wrong_volume|$volume|$actual"; exit 4; }
  label="$(docker volume inspect --format '{{index .Labels "com.docker.compose.project"}}' "$volume")"
  [[ "$label" == "$STACK_ID" ]] || { echo "FAIL|backup_volume_project_label_mismatch|$volume"; exit 4; }
  docker run --rm --network none --user 0:0 --entrypoint /bin/sh \
    -v "$volume:/source:ro" "$ARCHIVE_IMAGE" -c 'tar czf - -C /source .' \
    > "$OUT/$logical.tar.gz"
  tar tzf "$OUT/$logical.tar.gz" >/dev/null || { echo "FAIL|archive_corrupt|$logical"; exit 4; }
done

cp .env "$OUT/.env.private"
chmod 600 "$OUT/.env.private"
git rev-parse HEAD > "$OUT/git-head.txt" 2>/dev/null || echo 'unknown' > "$OUT/git-head.txt"

python3 - "$OUT" "$STACK_ID" <<'PY'
from datetime import datetime,timezone
from pathlib import Path
import json,sys
folder=Path(sys.argv[1]); stack=sys.argv[2]
files=['aiops.dump','n8n.dump','temporal.dump','temporal_visibility.dump',
       'glpi-mariadb.sql','aiops2-n8n-data.tar.gz','aiops2-glpi-data.tar.gz',
       'aiops2-grafana-data.tar.gz','aiops2-prometheus-data.tar.gz',
       '.env.private','git-head.txt']
missing=[name for name in files if not (folder/name).is_file() or (folder/name).stat().st_size==0]
if missing:
    raise SystemExit('FAIL|empty_or_missing_backup_files|'+','.join(missing))
manifest={'format_version':2,'stack_id':stack,'created_utc':datetime.now(timezone.utc).isoformat(),
          'contains_secrets':True,'backup_status':'COMPLETE','database_capture':'logical',
          'volume_capture':'online_snapshot','application_consistent':False,
          'files':files}
(folder/'BACKUP-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
PY
(
 cd "$OUT"
 find . -maxdepth 1 -type f ! -name SHA256SUMS ! -name .BACKUP_INCOMPLETE -print0 \
   | sort -z | xargs -0 sha256sum > SHA256SUMS
 sha256sum -c SHA256SUMS >/dev/null
)
rm -f "$OUT/.BACKUP_INCOMPLETE"
echo "BACKUP=PASS|stack_id=$STACK_ID|directory=$OUT"
echo 'PRIVATE_BACKUP=1'
echo 'WARNING: contains credentials, databases and service state; encrypt at rest. Never upload to GitHub.'
