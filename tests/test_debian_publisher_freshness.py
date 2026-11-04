"""Regression tests for Debian publisher freshness classification (offline only)."""
import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "deploy/debian-portal-preflight.py"
spec = importlib.util.spec_from_file_location("debian_preflight_freshness", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PublisherFreshnessTests(unittest.TestCase):
    def state(self, *, local=True, log=True, marker="PUBLISHED"):
        return {"local_report": {"fresh": local}, "publish_log_recent": log,
                "publish_last_class": marker, "publish_log_age_seconds": 116368}

    def test_old_published_marker_does_not_qualify_delivery(self):
        result = module.classify_publisher_freshness(self.state())
        self.assertEqual(result["delivery_state"], "RECENT_LOCAL_PUBLISH_ACTIVITY_ONLY")
        self.assertFalse(result["remote_receipt_verified"])
        stale = module.classify_publisher_freshness(self.state(log=False))
        self.assertEqual(stale["delivery_state"], "PUBLISH_LOG_STALE")
        self.assertFalse(stale["remote_receipt_verified"])

    def test_stale_local_report_blocks_even_if_log_recent(self):
        result = module.classify_publisher_freshness(self.state(local=False))
        self.assertEqual(result["delivery_state"], "LOCAL_REPORT_STALE")

    def test_explicit_publisher_failures_are_not_green(self):
        for marker in ("PUSH_REJECTED", "SSH_DENIED", "SSH_DNS_FAILURE",
                       "DIRTY_CHECKOUT", "GIT_FATAL"):
            with self.subTest(marker=marker):
                result = module.classify_publisher_freshness(self.state(marker=marker))
                self.assertEqual(result["delivery_state"], "PUBLISH_FAILURE")
                self.assertFalse(result["remote_receipt_verified"])

    def test_unknown_is_unverified(self):
        result = module.classify_publisher_freshness(self.state(marker="UNKNOWN"))
        self.assertEqual(result["delivery_state"], "PUBLISH_UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
