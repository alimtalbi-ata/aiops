#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

BACKUP_DIR="/home/aiops/aiops2-rebuild-kit/db-backup-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

echo "Sauvegarde dans : $BACKUP_DIR"

echo "=== POSTGRESQL AIOPS + N8N ==="

docker exec aiops2-rebuild-postgres sh -c '
  export PGUSER="${POSTGRES_USER:-postgres}"
  export PGPASSWORD="${POSTGRES_PASSWORD:-}"
  pg_dumpall -U "$PGUSER"
' > "$BACKUP_DIR/postgres-aiops-n8n.sql"

echo "=== POSTGRESQL TEMPORAL ==="

docker exec aiops2-rebuild-temporal-postgres sh -c '
  export PGUSER="${POSTGRES_USER:-postgres}"
  export PGPASSWORD="${POSTGRES_PASSWORD:-}"
  pg_dumpall -U "$PGUSER"
' > "$BACKUP_DIR/postgres-temporal.sql"

echo "=== MARIADB GLPI ==="

docker exec aiops2-rebuild-glpi-db sh -c '
  export MYSQL_PWD="${MARIADB_ROOT_PASSWORD:-${MYSQL_ROOT_PASSWORD:-}}"
  test -n "$MYSQL_PWD" || {
    echo "Mot de passe MariaDB root absent" >&2
    exit 1
  }

  mariadb-dump \
    --user=root \
    --all-databases \
    --single-transaction \
    --quick \
    --routines \
    --events \
    --triggers
' > "$BACKUP_DIR/mariadb-glpi.sql"

echo "=== VERIFICATION ==="

for f in "$BACKUP_DIR"/*.sql; do
  test -s "$f"
done

sha256sum "$BACKUP_DIR"/*.sql > "$BACKUP_DIR/SHA256SUMS"

ls -lh "$BACKUP_DIR"

echo
echo "SAUVEGARDE LOGIQUE TERMINEE"
echo "Dossier : $BACKUP_DIR"
