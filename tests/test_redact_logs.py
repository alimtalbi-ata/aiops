"""Regression tests for diagnostics redaction with exact secret-value matching."""
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("aiops_diagnostic_scrub", ROOT / "deploy" / "redact_logs.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DiagnosticRedactionTests(unittest.TestCase):
    def test_secrets_suppressed_even_without_labels(self):
        with TemporaryDirectory() as folder:
            env = Path(folder) / ".env"
            env.write_text(
                "AIOPS_INTERNAL_TOKEN=abcdef0123456789\n"
                "POSTGRES_PASSWORD=supersecret10\n"
                "OTHER_SETTING=nonsecret\n",
                encoding="utf-8",
            )
            values = MODULE.load_secret_values(env)
            sanitized = MODULE.scrub("internal=abcdef0123456789 password: supersecret10 other=nonsecret", values)
            self.assertNotIn("abcdef0123456789", sanitized)
            self.assertNotIn("supersecret10", sanitized)
            self.assertIn("nonsecret", sanitized)

    def test_bearer_and_url_credentials(self):
        value = MODULE.scrub("Bearer abc.123 postgres://user:p4ssword@db:5432/mydb", [])
        self.assertNotIn("abc.123", value)
        self.assertNotIn("p4ssword", value)
        self.assertIn("db:5432/mydb", value)

    def test_inline_assignment_and_option(self):
        value = MODULE.scrub("AIOPS_SECRET=abc123 API_KEY: 5678 --token abc456", [])
        for forbidden in ("abc123", "5678", "abc456"):
            self.assertNotIn(forbidden, value)

    def test_missing_env_lists_no_values(self):
        with TemporaryDirectory() as folder:
            self.assertEqual(MODULE.load_secret_values(Path(folder) / "missing.env"), [])


if __name__ == "__main__":
    unittest.main()
