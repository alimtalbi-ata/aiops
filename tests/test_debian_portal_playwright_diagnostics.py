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
