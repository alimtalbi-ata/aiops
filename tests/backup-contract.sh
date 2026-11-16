#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
for pattern in 'aiops.dump' 'n8n.dump' 'temporal.dump' 'glpi-mariadb.sql' 'aiops2-n8n-data' 'aiops2-glpi-data' 'aiops2-grafana-data' 'aiops2-prometheus-data' '.env.private' 'SHA256SUMS'; do
  grep -Fq "$pattern" deploy/backup.sh || { echo "FAIL|backup_missing|$pattern"; exit 1; }
done
grep -Fq 'CONFIRM_RESTORE' deploy/restore.sh
grep -Fq 'CONFIRM_TARGET_DATABASES' deploy/restore.sh
grep -Fq 'python3 deploy/verify_backup.py' deploy/restore.sh
grep -Fq 'CONFIRM_STACK_ID' deploy/restore.sh
grep -Fq 'CONFIRM_DATA_LOSS' deploy/restore.sh
grep -Fq 'RESTORE_VERIFY_ONLY=PASS' deploy/restore.sh
grep -Fq 'temporal_visibility.dump' deploy/backup.sh
grep -Fq 'temporal_visibility.dump' deploy/restore.sh
grep -Fq 'BACKUP-MANIFEST.json' deploy/backup.sh
grep -Fq 'AIOPS_STACK_ID' deploy/backup.sh
grep -Fq 'ux_evidence_source_external_identity' db/migrations/010_evidence_identity.sql
grep -Fq 'never upload' deploy/backup.sh || grep -Fq 'Never upload' deploy/backup.sh
grep -Fq 'backup_volume_project_label_mismatch' deploy/backup.sh
grep -Fq 'restore_volume_project_label_mismatch' deploy/restore.sh
echo 'BACKUP_RESTORE_CONTRACT=PASS'
