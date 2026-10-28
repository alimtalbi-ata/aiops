"""Unit-only registry/navigation tests; no external service is contacted."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from portal.platform_registry import build_portal_component_registry
from portal.portal_integrations import build_navigation, render_navigation_html, validate_browser_link


class PortalNavigationTests(unittest.TestCase):
    def test_all_services_unknown_without_observations(self):
        model = build_navigation({})
        self.assertEqual(model["entrypoint"], "http://10.79.94.202:17777/")
        self.assertEqual(model["navigation_mode"], "EXTERNAL_BROWSER_LINKS_ONLY_NO_PROXY")
        self.assertFalse(model["runtime_verified"])
        self.assertTrue(all(item["state"] == "UNKNOWN" for item in model["items"]))
        self.assertTrue(all(not item["runtime_authenticated"] for item in model["items"]))

    def test_operator_link_does_not_attest_service(self):
        model = build_navigation({"AIOPS_PORTAL_LINK_GRAFANA": "https://grafana.example.invalid/d/ops"})
        item = next(i for i in model["items"] if i["id"] == "grafana")
        self.assertEqual(item["external_link_state"], "CONFIGURED_UNVERIFIED")
        self.assertEqual(item["external_url"], "https://grafana.example.invalid/d/ops")
        self.assertEqual(item["state"], "UNKNOWN")
        self.assertFalse(item["route_mounted"])
        self.assertFalse(item["available_in_portal"])
        self.assertFalse(item["runtime_authenticated"])

    def test_https_with_credentials_rejected(self):
        with self.assertRaises(ValueError):
            validate_browser_link("https://admin:secret@grafana.example.invalid/")

    def test_script_and_scheme_relative_urls_rejected(self):
        for url in ("javascript:alert(1)", "//evil.example/", "data:text/html,evil",
                    "ftp://example.org/", "https://example.org/\r\nX-Test:1",
                    "https://example.org:99999/", "https://example.org/?token=secret",
                    "https://example.org/#access_token=secret", "https://example.org\\@evil/"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_browser_link(url)

    def test_http_requires_explicit_private_ip_opt_in(self):
        with self.assertRaises(ValueError):
            validate_browser_link("http://10.79.94.202:3000/")
        with self.assertRaises(ValueError):
            validate_browser_link("http://grafana.example.invalid/", allow_private_http=True)
        with self.assertRaises(ValueError):
            validate_browser_link("http://127.0.0.1:3000/", allow_private_http=True)
        with self.assertRaises(ValueError):
            validate_browser_link("http://8.8.8.8/", allow_private_http=True)
        self.assertEqual(validate_browser_link("http://10.79.94.202:3000/",
                                               allow_private_http=True),
                         "http://10.79.94.202:3000/")

    def test_http_opt_in_rejects_special_use_and_non_lan_ranges(self):
        # ipaddress.is_private is broader than operator-controlled LAN space.
        for url in (
            "http://192.0.0.1:3000/", "http://192.0.2.1:3000/",
            "http://198.18.0.1:3000/", "http://198.51.100.2:3000/",
            "http://203.0.113.9:3000/", "http://240.0.0.1:3000/",
            "http://169.254.1.1:3000/", "http://100.64.0.1:3000/",
            "http://172.15.255.255:3000/", "http://172.32.0.1:3000/",
            "http://[2001:db8::1]:3000/", "http://[::ffff:10.0.0.1]:3000/",
            "http://10.79.94.202.evil.example:3000/",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_browser_link(url, allow_private_http=True)

    def test_http_opt_in_accepts_rfc1918_and_ipv6_ula(self):
        for url in (
            "http://10.79.94.202:3000/", "http://172.16.0.1:3000/",
            "http://172.31.255.254:3000/", "http://192.168.1.2:3000/",
            "http://[fd00::1]:3000/",
        ):
            with self.subTest(url=url):
                self.assertEqual(validate_browser_link(url, allow_private_http=True), url)

    def test_rejected_http_address_does_not_leak_into_navigation(self):
        model = build_navigation({
            "AIOPS_PORTAL_ALLOW_HTTP_LINKS": "true",
            "AIOPS_PORTAL_LINK_N8N": "http://192.0.2.1:5678/",
        })
        item = next(i for i in model["items"] if i["id"] == "n8n")
        self.assertEqual(item["external_link_state"], "REJECTED_CONFIGURATION")
        self.assertIsNone(item["external_url"])
        self.assertNotIn("192.0.2.1", render_navigation_html(model))

    def test_bad_config_fails_closed_without_leaking_url(self):
        model = build_navigation({"AIOPS_PORTAL_LINK_N8N": "javascript:alert(1)"})
        item = next(i for i in model["items"] if i["id"] == "n8n")
        self.assertEqual(item["external_link_state"], "REJECTED_CONFIGURATION")
        self.assertIsNone(item["external_url"])
        self.assertNotIn("javascript:", render_navigation_html(model))

    def test_link_html_is_escaped_and_opens_safely(self):
        model = build_navigation({"AIOPS_PORTAL_LINK_GLPI": "https://glpi.example.invalid/a&b"})
        markup = render_navigation_html(model)
        self.assertIn('href="https://glpi.example.invalid/a&amp;b"', markup)
        self.assertIn('rel="noopener noreferrer"', markup)
        self.assertIn('referrerpolicy="no-referrer"', markup)
        self.assertNotIn('href="https://glpi.example.invalid/a&b"', markup)

    def test_stale_and_unauthenticated_observations_remain_unknown(self):
        now = "2026-10-27T20:00:00Z"
        old = {"state": "OK", "observed_at": "2026-10-27T19:00:00Z",
               "authenticated": True}
        unauth = {"state": "OK", "observed_at": now, "authenticated": False}
        model = build_portal_component_registry({"n8n": old, "grafana": unauth},
                                                now_utc=now)
        rows = {i["id"]: i for i in model["items"]}
        self.assertEqual(rows["n8n"]["state"], "UNKNOWN")
        self.assertEqual(rows["grafana"]["state"], "UNKNOWN")

    def test_unexpected_observation_identity_rejected(self):
        with self.assertRaises(ValueError):
            build_portal_component_registry({"unknown-service": {}})


if __name__ == "__main__":
    unittest.main()
