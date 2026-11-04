"""Regression tests: Chromium diagnostics must be redacted and fail closed."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

SCRIPT = Path(__file__).resolve().parents[1] / "deploy/debian-portal-playwright-snapshot.py"
spec = importlib.util.spec_from_file_location("portal_playwright_diagnostics", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def request(url, failure="net::ERR_ABORTED", resource_type="fetch"):
    return SimpleNamespace(url=url, failure=failure, resource_type=resource_type)


def test_expected_session_request_class_without_query_leak():
    data = module.request_diagnostic(
        request("http://127.0.0.1:7777/api/portal/session?token=TOPSECRET"),
        "04-connections")
    assert data == {"stage": "04-connections", "endpoint_class": "anonymous_session",
                    "resource_type": "fetch", "failure_class": "aborted"}
    assert "TOPSECRET" not in str(data)
    assert "/api/portal/session" not in str(data)


def test_unrelated_api_failure_remains_distinct():
    data = module.request_diagnostic(
        request("http://127.0.0.1:7777/api/private?password=TOPSECRET",
                "net::ERR_CONNECTION_REFUSED", "xhr"), "04-connections")
    assert data["endpoint_class"] == "other_api"
    assert data["failure_class"] == "connection"
    assert "TOPSECRET" not in str(data)


def test_arbitrary_url_and_type_never_persisted():
    data = module.request_diagnostic(
        request("https://example.invalid/secret/path?credential=TOPSECRET",
                "net::ERR_FAILED", "private_custom_type"), "mobile-390px")
    assert data["endpoint_class"] == "other_resource"
    assert data["resource_type"] == "other"
    assert data["failure_class"] == "other_request_failure"
    assert "secret" not in str(data).lower()
    assert "TOPSECRET" not in str(data)


def test_only_exact_session_console_resource_is_expected():
    origin = "http://127.0.0.1:7777"
    def console(url):
        return SimpleNamespace(
            text="Failed to load resource: the server responded with a status of 401",
            location={"url": url})
    assert module.is_expected_session_401_console(
        console(origin + "/api/portal/session"), True, origin)
    assert not module.is_expected_session_401_console(
        console(origin + "/api/private"), True, origin)
    assert not module.is_expected_session_401_console(
        console(origin + "/api/portal/session"), False, origin)
    assert not module.is_expected_session_401_console(
        console(origin + "/api/portal/session?token=SECRET"), True, origin)
    assert not module.is_expected_session_401_console(
        console("https://other.invalid/api/portal/session"), True, origin)
    assert not module.is_expected_session_401_console(
        SimpleNamespace(text=console(origin).text, location={}), True, origin)


def test_real_chromium_401_console_resource_semantics():
    """Exercise actual Chromium console locations, not synthetic SimpleNamespace."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    from playwright.sync_api import sync_playwright

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/api/portal/session", "/api/unrelated"):
                self.send_response(401)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Unauthorized")
            elif self.path == "/":
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<html><body>Diagnostic test</body></html>")
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                messages = []
                statuses = []
                page.on("console", lambda msg: messages.append(msg) if msg.type == "error" else None)
                page.on("response", lambda resp: statuses.append(
                    (resp.url, resp.status)))
                page.goto(origin + "/")
                # Separate requests and allow Chromium to emit its resource diagnostics.
                page.evaluate("""async () => {
                    await fetch('/api/portal/session');
                    await fetch('/api/unrelated');
                }""")
                page.wait_for_timeout(200)
                assert (origin + "/api/portal/session", 401) in statuses
                assert (origin + "/api/unrelated", 401) in statuses
                resource_errors = [m for m in messages
                                   if module.classify_console_error(m) == "http_401_resource"]
                assert resource_errors, "Chromium did not emit a 401 resource console error"
                # An unrelated 401 must never be waived by the session's 401.
                assert any(not module.is_expected_session_401_console(m, True, origin)
                           for m in resource_errors), (
                    "Unrelated 401 was incorrectly classified as session 401")
                # Verify whether real Chromium exposes a session resource URL at all.
                # If this fails, do not merge an unproven location-based exception.
                assert any(module.is_expected_session_401_console(m, True, origin)
                           for m in resource_errors), (
                    "Chromium console location does not identify session resource")
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
