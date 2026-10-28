"""Real GLPI HTTP negative integration: never a synthetic ticket or LIVE proof.

This suite runs ONLY inside the isolated GitHub Actions Docker network with
the actual glpi/glpi and MariaDB containers. It deliberately uses invalid
CI-only credentials and therefore cannot attest a successful ticket read.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from shared.glpi_ticket_read import GLPIUnverified, read_ticket

BASE = "http://aiops2-glpi"
TICKET_ID = 2147483647
CI_ENV = {
    "CI": "true",
    "AIOPS_GLPI_API_BASE_URL": BASE + "/apirest.php",
    "AIOPS_GLPI_APP_TOKEN": "CI_ONLY_INVALID_APP_TOKEN_20261028",
    "AIOPS_GLPI_SESSION_TOKEN": "CI_ONLY_INVALID_SESSION_TOKEN_20261028",
    "AIOPS_GLPI_ENTITY_ID": "0",
}


class GLPIRealHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("AIOPS_GLPI_REAL_CI") != "true":
            raise RuntimeError("BLOCKED: real GLPI container CI is required")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        cls.login_html = None
        last_error = "not ready"
        for _ in range(30):
            try:
                with opener.open(BASE + "/", timeout=4) as response:
                    content = response.read(65536)
                    if response.status == 200 and b"glpi" in content.lower():
                        cls.login_html = content
                        break
                    title_match = re.search(rb"<title[^>]*>([^<]{0,100})", content, re.I)
                    title = title_match.group(1).decode("ascii", "replace") if title_match else "none"
                    title = re.sub(r"[^A-Za-z0-9 .,_/-]", "?", title)
                    last_error = ("status=" + str(response.status)
                                  + " type=" + response.headers.get("Content-Type", "missing")
                                  + " title=" + title)
            except urllib.error.HTTPError as exc:
                last_error = "HTTP_" + str(exc.code) + " type=" + exc.headers.get("Content-Type", "missing")
            except OSError as exc:
                last_error = type(exc).__name__
            time.sleep(3)
        if cls.login_html is None:
            raise AssertionError("BLOCKED: real GLPI HTTP not ready: " + last_error)

    def test_real_glpi_web_frontend_is_reachable(self):
        self.assertIn(b"glpi", self.login_html.lower())

    def test_real_glpi_api_rejects_invalid_ci_session(self):
        """Require an actual GLPI API JSON denial, not just a web login page."""
        req = urllib.request.Request(
            BASE + "/apirest.php/Ticket/" + str(TICKET_ID),
            headers={
                "Accept": "application/json",
                "App-Token": CI_ENV["AIOPS_GLPI_APP_TOKEN"],
                "Session-Token": CI_ENV["AIOPS_GLPI_SESSION_TOKEN"],
            },
            method="GET",
        )
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            type("NoRedirect", (urllib.request.HTTPRedirectHandler,),
                 {"redirect_request": lambda self, *args: None})(),
        )
        try:
            with opener.open(req, timeout=5) as response:
                status = response.status
                ctype = response.headers.get("Content-Type", "")
                raw = response.read(65537)
        except urllib.error.HTTPError as exc:
            status = exc.code
            ctype = exc.headers.get("Content-Type", "")
            raw = exc.read(65537)
        self.assertLessEqual(len(raw), 65536, "BLOCKED: oversized GLPI API response")
        self.assertEqual(ctype.split(";", 1)[0].strip().lower(),
                         "application/json", "BLOCKED: GLPI REST API unavailable")
        payload = json.loads(raw)
        self.assertIn(status, (400, 401, 403), "BLOCKED: unexpected API auth status")
        self.assertIsInstance(payload, (dict, list))
        self.assertNotEqual(payload, {"id": TICKET_ID})
        self.assertIn("ERROR_", json.dumps(payload).upper(),
                      "BLOCKED: API did not return a recognizable GLPI error")

    def test_reader_fails_closed_against_real_glpi(self):
        with self.assertRaises(GLPIUnverified):
            read_ticket(TICKET_ID, env=CI_ENV, mode="DEMO")

    def test_live_refused_with_same_real_endpoint_config(self):
        with self.assertRaisesRegex(GLPIUnverified, "LIVE"):
            read_ticket(TICKET_ID, env=CI_ENV, mode="LIVE")


if __name__ == "__main__":
    unittest.main()
