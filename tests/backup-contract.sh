#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
for pattern in 'aiops.dump' 'n8n.dump' 'temporal.dump' 'glpi-mariadb.sql' 'aiops2-n8n-data' 'aiops2-glpi-data' 'aiops2-grafana-data' 'aiops2-prometheus-data' '.env.private' 'SHA256SUMS'; do
  grep -Fq "$pattern" deploy/backup.sh || { echo "FAIL|backup_missing|$pattern"; exit 1; }
done
grep -Fq 'CONFIRM_RESTORE' deploy/restore.sh
grep -Fq 'CONFIRM_TARGET_DATABASES' deploy/restore.sh
grep -Fq 'sha256sum -c SHA256SUMS' deploy/restore.sh
grep -Fq 'never upload' deploy/backup.sh || grep -Fq 'Never upload' deploy/backup.sh
echo 'BACKUP_RESTORE_CONTRACT=PASS'
