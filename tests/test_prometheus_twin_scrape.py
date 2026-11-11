"""No-network, no-production tests for the Prometheus Twin credential contract."""
from pathlib import Path
import os
import stat
import tempfile
import unittest
from scripts.prepare_prometheus_twin_scrape import prepare, Blocked

ROOT = Path(__file__).resolve().parents[1]

class PrometheusTwinScrapeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.env = root / ".env"
        self.out = root / ".local/prometheus/twin-metrics-token"
        self.env.write_text("AIOPS_ADMIN_TOKEN=admin-ephemeral-only\n"
                            "AIOPS_INTERNAL_TOKEN=internal-ephemeral-only\n")
        self.env.chmod(0o600)

    def test_provision_and_check_distinct_private_credential(self):
        with self.assertRaisesRegex(Blocked, "missing_or_invalid"):
            prepare(self.env, self.out)
        prepare(self.env, self.out, provision=True)
        token = self.out.read_text()
        self.assertEqual(len(token), 64)
        self.assertNotIn(token, ("admin-ephemeral-only", "internal-ephemeral-only"))
        self.assertEqual(self.out.stat().st_mode & 0o777, 0o644)
        self.assertEqual(self.out.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.out.parent.parent.stat().st_mode & 0o777, 0o700)
        self.assertIn("AIOPS_TWIN_METRICS_TOKEN=" + token, self.env.read_text())
        self.assertEqual(self.env.stat().st_mode & 0o777, 0o600)
        prepare(self.env, self.out, check=True)
        self.out.write_text("stale")
        with self.assertRaisesRegex(Blocked, "stale"):
            prepare(self.env, self.out, check=True)

    def test_reject_admin_reuse_and_symlink(self):
        self.env.write_text(self.env.read_text() + "AIOPS_TWIN_METRICS_TOKEN=admin-ephemeral-only\n")
        with self.assertRaisesRegex(Blocked, "not_distinct"):
            prepare(self.env, self.out)
        self.env.unlink()
        self.env.symlink_to(Path(self.tmp.name) / "other")
        with self.assertRaisesRegex(Blocked, "unsafe_env"):
            prepare(self.env, self.out, provision=True)

    def test_prometheus_config_uses_file_not_inline_secret(self):
        config = (ROOT / "config/prometheus/prometheus.yml").read_text()
        compose = (ROOT / "compose.yml").read_text()
        self.assertIn("credentials_file: /run/aiops2/twin-metrics-token", config)
        self.assertIn("source: ./.local/prometheus/twin-metrics-token", compose)
        self.assertIn("create_host_path: false", compose)
        self.assertIn("AIOPS_TWIN_METRICS_TOKEN_required", compose)
        self.assertNotIn("bearer_token:", config)
        self.assertIn(".local/", (ROOT / ".gitignore").read_text())

if __name__ == "__main__":
    unittest.main()
