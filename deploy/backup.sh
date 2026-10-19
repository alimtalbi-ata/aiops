#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
[[ -f .env ]] || { echo 'FAIL|missing_env'; exit 2; }
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${1:-$ROOT/backups/aiops2-$STAMP}"
mkdir -p "$OUT"; chmod 700 "$OUT"
# Logical dumps cover the databases; volume archives cover service-owned state.
docker compose --env-file .env exec -T aiops2-postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' > "$OUT/aiops.dump"
docker compose --env-file .env exec -T aiops2-postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d n8n --format=custom' > "$OUT/n8n.dump"
docker compose --env-file .env exec -T aiops2-temporal-postgres pg_dump -U temporal -d temporal --format=custom > "$OUT/temporal.dump"
docker compose --env-file .env exec -T aiops2-glpi-db sh -c 'mariadb-dump -uroot -p"$MARIADB_ROOT_PASSWORD" --single-transaction --routines --events --all-databases' > "$OUT/glpi-mariadb.sql"
for volume in aiops2-n8n-data aiops2-glpi-data aiops2-grafana-data aiops2-prometheus-data; do
  docker run --rm -v "$volume:/source:ro" -v "$OUT:/backup" alpine:3.22 sh -c "tar czf /backup/$volume.tar.gz -C /source ."
done
cp .env "$OUT/.env.private"; chmod 600 "$OUT/.env.private"
git rev-parse HEAD > "$OUT/git-head.txt" 2>/dev/null || echo unknown > "$OUT/git-head.txt"
(
 cd "$OUT"
 find . -maxdepth 1 -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
)
echo "BACKUP=$OUT"
echo 'PRIVATE_BACKUP=1'
echo 'WARNING: contains credentials, database dumps and service state; encrypt at rest and store offline. Never upload to GitHub.'
