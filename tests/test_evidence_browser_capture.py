import importlib.util
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "demo" / "evidence_browser_capture.py"
spec = importlib.util.spec_from_file_location("evidence_browser_capture", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def plan():
    return {
        "schema_version": 1, "run_id": "RUN-001", "incident_id": "INC-001",
        "ticket_id": "TCK-001", "session_label": "operator-unreviewed",
        "captures": [
            {"service": s, "url": "https://example.invalid/" + s,
             "allowed_origin": "https://example.invalid",
             "proof_selector": "#run-id", "proof_text": "RUN-001",
             "redact_selectors": [".sensitive"], "approved_get_urls": []}
            for s in module.SERVICES
        ],
    }

class BrowserCaptureTests(unittest.TestCase):
    def test_valid_plan(self):
        self.assertEqual(len(module.validate_plan(plan())), 5)

    def test_dry_run_never_opens_browser(self):
        with patch.dict(os.environ, {"CI": "true", "AIOPS_CAPTURE_OPERATOR_APPROVED": "YES"}):
            result = module.capture(plan(), "/missing/output", "/missing/states")
        self.assertEqual(result["status"], "DRY_RUN")
        self.assertEqual(result["captures_performed"], 0)

    def test_ci_capture_forbidden_before_browser(self):
        with patch.dict(os.environ, {"CI": "true", "AIOPS_CAPTURE_OPERATOR_APPROVED": "YES"}):
            with self.assertRaisesRegex(ValueError, "forbidden"):
                module.capture(plan(), "/missing/output", "/missing/states", approved=True)

    def test_operator_authorization_required(self):
        with patch.dict(os.environ, {"CI": "false", "AIOPS_CAPTURE_OPERATOR_APPROVED": ""}):
            with self.assertRaisesRegex(ValueError, "authorization"):
                module.capture(plan(), "/missing/output", "/missing/states", approved=True)

    def test_duplicate_service(self):
        p = plan()
        p["captures"][1]["service"] = "portal"
        with self.assertRaises(ValueError):
            module.validate_plan(p)

    def test_cross_origin_denied(self):
        p = plan()
        p["captures"][0]["url"] = "https://attacker.invalid/portal"
        with self.assertRaises(ValueError):
            module.validate_plan(p)

    def test_url_credentials_denied(self):
        p = plan()
        p["captures"][0]["url"] = "https://user:pass@example.invalid/portal"
        with self.assertRaises(ValueError):
            module.validate_plan(p)

    def test_url_query_denied(self):
        p = plan()
        p["captures"][0]["url"] = "https://example.invalid/portal?token=secret"
        with self.assertRaises(ValueError):
            module.validate_plan(p)

    def test_unapproved_get_denied(self):
        item = plan()["captures"][0]
        self.assertTrue(module.permits(item, item["url"], "GET", True, True))
        self.assertFalse(module.permits(item, item["url"], "POST", True, True))
        self.assertFalse(module.permits(item, item["url"], "GET", True, False))
        self.assertFalse(module.permits(item, "https://example.invalid/private", "GET", False, False))
        self.assertFalse(module.permits(item, "https://attacker.invalid/", "GET", False, False))

    def test_proof_must_bind_incident_run_or_ticket(self):
        p = plan()
        p["captures"][0]["proof_text"] = "READY"
        with self.assertRaises(ValueError):
            module.validate_plan(p)

    def test_selector_injection_denied(self):
        p = plan()
        p["captures"][0]["redact_selectors"] = ["button:has-text('Delete')"]
        with self.assertRaises(ValueError):
            module.validate_plan(p)

    def test_get_allowlist_exact_only(self):
        p = plan()
        item = p["captures"][0]
        item["approved_get_urls"] = ["https://example.invalid/app.css"]
        module.validate_plan(p)
        self.assertTrue(module.permits(item, "https://example.invalid/app.css", "GET", False, False))
        self.assertFalse(module.permits(item, "https://example.invalid/app.css?token=secret", "GET", False, False))
        self.assertFalse(module.permits(item, "https://example.invalid/app.css", "POST", False, False))

    def test_missing_mask_denied(self):
        p = plan()
        p["captures"][0]["redact_selectors"] = []
        with self.assertRaises(ValueError):
            module.validate_plan(p)

    def test_proof_mask_overlap_denied(self):
        p = plan()
        p["captures"][0]["redact_selectors"] = ["#run-id"]
        with self.assertRaises(ValueError):
            module.validate_plan(p)

    def test_world_readable_capture_dir_denied(self):
        p = plan()
        with tempfile.TemporaryDirectory() as td:
            os.chmod(td, 0o755)
            try:
                with patch.dict(os.environ, {"CI": "false", "AIOPS_STAR_NO_RUNTIME": "0",
                                             "AIOPS_CAPTURE_OPERATOR_APPROVED": "YES"}):
                    with self.assertRaisesRegex(ValueError, "permissions"):
                        module.capture(p, td, td, approved=True)
            finally:
                os.chmod(td, 0o700)

    def test_missing_session_state_fails_before_browser(self):
        p = plan()
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"CI": "false", "AIOPS_STAR_NO_RUNTIME": "0",
                                         "AIOPS_CAPTURE_OPERATOR_APPROVED": "YES"}):
                with self.assertRaisesRegex(ValueError, "session state"):
                    module.capture(p, td, td, approved=True)

    def test_context_fence_denies_popup_and_unapproved_requests(self):
        item = plan()["captures"][0]
        item["approved_get_urls"] = ["https://example.invalid/app.css"]

        class Request:
            def __init__(self, url, method="GET", navigation=False, frame=None):
                self.url, self.method, self.navigation, self.frame = url, method, navigation, frame
            def is_navigation_request(self):
                return self.navigation

        class Route:
            def __init__(self, request):
                self.request = request
                self.result = None
            def continue_(self):
                self.result = "continued"
            def abort(self):
                self.result = "aborted"

        class Context:
            def route(self, pattern, handler):
                self.http = handler
            def route_web_socket(self, pattern, handler):
                self.ws = handler

        class Page:
            main_frame = object()

        context, page = Context(), Page()
        blocked = module.install_network_fence(context, page, item)
        requests = [
            (Request(item["url"], navigation=True, frame=page.main_frame), "continued"),
            (Request(item["url"], navigation=True, frame=object()), "aborted"),
            (Request("https://example.invalid/app.css"), "continued"),
            (Request("https://example.invalid/secret"), "aborted"),
            (Request("https://evil.invalid/collect", method="POST"), "aborted"),
        ]
        for request, expected in requests:
            with self.subTest(url=request.url, expected=expected):
                route = Route(request)
                context.http(route)
                self.assertEqual(route.result, expected)
        self.assertEqual(len(blocked), 3)
        class Socket:
            closed = False
            def close(self):
                self.closed = True
        socket = Socket()
        context.ws(socket)
        self.assertTrue(socket.closed)
        self.assertEqual(len(blocked), 4)

    def test_missing_websocket_fence_blocks_capture(self):
        class Context:
            def route(self, pattern, handler):
                raise AssertionError("HTTP route must not install before WS capability check")
        with self.assertRaisesRegex(ValueError, "WebSocket interception unavailable"):
            module.install_network_fence(Context(), object(), plan()["captures"][0])

if __name__ == "__main__":
    unittest.main()
