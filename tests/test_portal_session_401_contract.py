"""Fail-closed regression tests for anonymous Portal session HTTP 401.

No Playwright installation, host, credentials or LIVE effects required.
Run: python3 -m unittest discover -s tests -p 'test_portal_session_401_contract.py'
"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "deploy" / "debian-portal-playwright-snapshot.py"
spec = importlib.util.spec_from_file_location("portal_snapshot_contract", SCRIPT)
snapshot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot)
ORIGIN = "http://127.0.0.1:7777"


def console(url, text="Failed to load resource: the server responded with a status of 401"):
    return SimpleNamespace(text=text, location={"url": url})


class Session401ContractTests(unittest.TestCase):
    def test_exact_anonymous_session_401_is_expected_only_when_observed(self):
        msg = console(ORIGIN + "/api/portal/session")
        self.assertTrue(snapshot.is_expected_session_401_console(msg, True, ORIGIN))
        self.assertFalse(snapshot.is_expected_session_401_console(msg, False, ORIGIN))

    def test_no_global_401_whitelist(self):
        for url in (
            ORIGIN + "/api/glpi/tickets",
            ORIGIN + "/api/portal/session/other",
            ORIGIN + "/api/portal/session?token=secret",
            ORIGIN + "/api/portal/session#fragment",
            "http://localhost:7777/api/portal/session",
            "http://127.0.0.1:7778/api/portal/session",
            "https://127.0.0.1:7777/api/portal/session",
            "http://attacker.invalid/api/portal/session",
            "http://user:pass@127.0.0.1:7777/api/portal/session",
        ):
            with self.subTest(url=url.split("?")[0]):
                self.assertFalse(snapshot.is_expected_session_401_console(
                    console(url), True, ORIGIN))

    def test_other_console_errors_fail_closed(self):
        for text in (
            "Failed to load resource: the server responded with a status of 403",
            "Failed to load resource: the server responded with a status of 404",
            "Uncaught TypeError: Cannot read properties of undefined",
        ):
            with self.subTest(text=text):
                self.assertFalse(snapshot.is_expected_session_401_console(
                    console(ORIGIN + "/api/portal/session", text), True, ORIGIN))

    def test_missing_or_ambiguous_console_location_fails_closed(self):
        for location in (None, {}, {"url": ""}, {"url": 42}, {"url": ORIGIN + "/api/portal/session?x=1"}):
            with self.subTest(location=location):
                msg = SimpleNamespace(text="Failed to load resource: 401", location=location)
                self.assertFalse(snapshot.is_expected_session_401_console(msg, True, ORIGIN))

    def test_failed_requests_never_waived_by_session_401(self):
        request = SimpleNamespace(url=ORIGIN + "/api/portal/session",
                                  resource_type="fetch", failure="net::ERR_ABORTED")
        diagnostic = snapshot.request_diagnostic(request, "04-connections")
        self.assertEqual(diagnostic["failure_class"], "aborted")
        self.assertEqual(diagnostic["endpoint_class"], "anonymous_session")
        self.assertNotIn("url", diagnostic)
        self.assertNotIn("failure", diagnostic)


if __name__ == "__main__":
    unittest.main()
