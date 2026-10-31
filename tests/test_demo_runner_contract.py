import contextlib
import importlib.util
import io
import pathlib
import sys
import unittest
from unittest.mock import patch

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "run-acme-demo.py"
SPEC = importlib.util.spec_from_file_location("aiops_demo_runner", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DemoRunnerContractTests(unittest.TestCase):
    def test_requires_explicit_synthetic_confirmation_before_network(self):
        stderr = io.StringIO()
        with patch.object(sys, "argv", ["run-acme-demo.py"]), \
             patch.object(MODULE, "request_json", side_effect=AssertionError("network must not be called")), \
             contextlib.redirect_stderr(stderr):
            self.assertEqual(MODULE.main(), 2)
        self.assertIn("confirm-synthetic-demo", stderr.getvalue())

    def test_refuses_unconfigured_provider_before_creating_incident(self):
        stderr = io.StringIO()
        env = {
            "AIOPS_INTERNAL_TOKEN": "ci-token-value-with-more-than-32-characters",
            "AIOPS_DEMO_PROVIDER_KIND": "UNCONFIGURED",
        }
        with patch.dict("os.environ", env, clear=True), \
             patch.object(sys, "argv", ["run-acme-demo.py", "--confirm-synthetic-demo"]), \
             patch.object(MODULE, "request_json", side_effect=AssertionError("network must not be called")), \
             contextlib.redirect_stderr(stderr):
            self.assertEqual(MODULE.main(), 2)
        self.assertIn("AIOPS_DEMO_PROVIDER_KIND", stderr.getvalue())

    def test_test_provider_requires_explicit_non_customer_override(self):
        stderr = io.StringIO()
        env = {
            "AIOPS_INTERNAL_TOKEN": "ci-token-value-with-more-than-32-characters",
            "AIOPS_DEMO_PROVIDER_KIND": "TEST_PROVIDER",
        }
        with patch.dict("os.environ", env, clear=True), \
             patch.object(sys, "argv", ["run-acme-demo.py", "--confirm-synthetic-demo"]), \
             patch.object(MODULE, "request_json", side_effect=AssertionError("network must not be called")), \
             contextlib.redirect_stderr(stderr):
            self.assertEqual(MODULE.main(), 2)
        self.assertIn("TEST_PROVIDER", stderr.getvalue())

    def test_missing_usage_and_cost_remain_unknown(self):
        summary = MODULE.usage_summary([{"model_invocation": {
            "usage_source": "unavailable", "total_tokens": None, "cost_usd": None
        }}])
        self.assertIsNone(summary["total_tokens"])
        self.assertIsNone(summary["cost_usd"])
        self.assertEqual(summary["usage_source"], "unknown")


if __name__ == "__main__":
    unittest.main()
