"""Static safe-gate only; never starts Docker or writes host DB."""
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
SCRIPT=(ROOT/'deploy/debian-acme-sandbox-upgrade.sh').read_text()
ENTRY=(ROOT/'deploy/deploy-demo-studio-v2.sh').read_text()
MANIFEST=json.loads((ROOT/'deploy/debian-acme-sandbox-release.json').read_text())
class SafeUpgrade(unittest.TestCase):
    def test_manifest_disabled_until_exact_head_and_host_backup(self):
        self.assertIs(MANIFEST['enabled'],False)
        self.assertEqual(MANIFEST['schema'],'aiops.debian-acme-sandbox-release-intent.v1')
    def test_only_existing_five_services_no_portal_recreate(self):
        self.assertIn('services="core twin policy worker simulator"',SCRIPT)
        self.assertIn('up -d --no-deps --no-build --force-recreate',SCRIPT)
        self.assertNotIn('up -d --no-deps --no-build --force-recreate aiops2-portal',SCRIPT)
        self.assertNotIn('docker run ',SCRIPT)
        self.assertNotIn('docker stop ',SCRIPT)
        self.assertNotIn('down -v',SCRIPT)
        self.assertNotIn('docker system prune',SCRIPT)
    def test_pg16_backup_before_migration_and_fail_closed(self):
        self.assertLess(SCRIPT.index('pg_dump -U aiops'),SCRIPT.index('psql -U aiops -d aiops -v ON_ERROR_STOP=1'))
        self.assertIn('pg_restore --list',SCRIPT)
        self.assertIn('backup_sha',SCRIPT)
        self.assertIn('rollback_status',SCRIPT)
        self.assertIn('image_changed',SCRIPT)
        self.assertIn('source_sha',SCRIPT)
    def test_terminal_migration_and_disposable_pg16_restore_before_mutation(self):
        self.assertIn('for n in 011 012 013 014 015 016 017 018; do', SCRIPT)
        self.assertIn('018_acme_sandbox_terminal_ticket_receipt.sql', SCRIPT)
        self.assertIn('restore_db="aiops_acme_restore_', SCRIPT)
        self.assertIn('NO_GO_SCRATCH_DB_ALREADY_EXISTS', SCRIPT)
        self.assertIn('NO_GO_RESTORE_DISK_HEADROOM', SCRIPT)
        self.assertIn('pg_restore -U aiops -d "$restore_db"', SCRIPT)
        self.assertIn('pg16_scratch_restore', SCRIPT)
        self.assertLess(SCRIPT.index('pg_restore -U aiops -d "$restore_db"'),
                        SCRIPT.index('psql -U aiops -d aiops -v ON_ERROR_STOP=1'))
        self.assertLess(SCRIPT.index('restore_status=PASS'),
                        SCRIPT.index('mutated=1\ncompose -f'))
        self.assertIn('if [ "$restore_created" = 1 ]; then', SCRIPT)

    def test_private_key_and_manifest_gated_poller(self):
        self.assertIn('acme-twin-hmac.key',SCRIPT)
        self.assertIn('os.fchmod(f.fileno(),0o600)',SCRIPT)
        self.assertIn('AIOPS_ACME_SANDBOX_ENABLED',SCRIPT)
        self.assertIn('if [ "$acme_enabled" = yes ] && [ "$status" -eq 0 ]',ENTRY)
        self.assertIn('if [ "$status" -eq 0 ]; then',ENTRY)
if __name__=='__main__':unittest.main()
