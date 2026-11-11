"""Regression contracts for the legacy Debian Portal deploy fail-closed preflight.

Static checks only: NEVER invoke Docker or the Debian host from CI.
"""
from pathlib import Path
import subprocess
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / "deploy/debian-portal-deploy.sh"


class PortalDeploySafetyTests(unittest.TestCase):
    def test_shell_syntax(self):
        result = subprocess.run(["bash", "-n", str(SCRIPT)],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_mounted_portal_cannot_be_recreated_by_legacy_path(self):
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("NO_GO_PERSISTENT_MOUNTS_REQUIRE_BACKUP_AND_RESTORE", script)
        self.assertIn('if [ "$MOUNT_COUNT" != 0 ]; then', script)
        self.assertLess(script.index('if [ "$MOUNT_COUNT" != 0 ]; then'),
                        script.index('docker build --quiet'))

    def test_missing_healthcheck_fails_before_build(self):
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("NO_GO_DOCKER_HEALTHCHECK_UNAVAILABLE_OR_UNHEALTHY", script)
        self.assertLess(script.index('if [ "$HEALTH_STATUS" != healthy ]; then'),
                        script.index('docker build --quiet'))

    def test_no_automatic_reset_or_volume_deletion(self):
        script = SCRIPT.read_text(encoding="utf-8")
        for forbidden in ("git reset --hard", "git clean -fd", "docker volume rm",
                          "docker compose down -v"):
            self.assertNotIn(forbidden, script)


if __name__ == "__main__":
    unittest.main()
