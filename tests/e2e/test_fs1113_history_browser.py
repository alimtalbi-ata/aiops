"""FS1113 browser regression on an isolated candidate only.

Run with PORTAL_CANDIDATE_URL=http://127.0.0.1:<candidate-port>
python -m unittest tests.e2e.test_fs1113_history_browser

The target must be an isolated non-production candidate. No authentication bypass:
supply a Playwright storage-state file for the authorized test identity if required.
"""
import json
import os
import unittest
from urllib.parse import parse_qs, urlparse

URL = os.environ.get("PORTAL_CANDIDATE_URL", "").rstrip("/")
STORAGE = os.environ.get("PORTAL_TEST_STORAGE_STATE")
METRICS = ("availability", "scrape_duration")
WINDOWS = ("1h", "6h", "24h")


def fixture(metric, window):
    return {
        "metric": metric, "window": window, "step_seconds": 60,
        "series": [
            {"job": "job-%d" % i, "instance": "instance-%d" % i,
             "points": [[1000, i + 1], [1060, i + 2]]}
            for i in range(5)
        ],
    }


@unittest.skipUnless(URL and os.environ.get("PORTAL_CANDIDATE_ISOLATED") == "1",
                     "requires explicit isolated candidate URL and flag")
class HistoryBrowserRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def open_candidate(self, mobile=False):
        options = {"viewport": {"width": 390, "height": 844}} if mobile else {}
        if STORAGE:
            options["storage_state"] = STORAGE
        context = self.browser.new_context(**options)
        page = context.new_page()
        requests = []

        def route_handler(route):
            parsed = urlparse(route.request.url)
            query = parse_qs(parsed.query)
            metric = query.get("metric", [""])[0]
            window = query.get("window", [""])[0]
            requests.append((metric, window))
            if metric not in METRICS or window not in WINDOWS:
                route.fulfill(status=400, body="invalid fixture")
                return
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(fixture(metric, window)))

        page.route("**/api/fs1089/prometheus/history?*", route_handler)
        page.goto(URL + "/explorer/visual", wait_until="domcontentloaded")
        self.assertEqual(page.locator("#history-chart").count(), 1,
                         "candidate route or authenticated session unavailable")
        page.wait_for_function("document.querySelector('#history-status')?.textContent.includes('5 séries')")
        return context, page, requests

    def assert_five(self, page):
        self.assertEqual(page.locator("#history-legend > span").count(), 5)
        self.assertEqual(page.locator("#history-chart path").count(), 5)

    def test_all_metrics_and_windows_with_refresh(self):
        context, page, requests = self.open_candidate()
        try:
            for metric in METRICS:
                page.locator("#history-metric").select_option(metric)
                for window in WINDOWS:
                    page.locator("#history-window").select_option(window)
                    page.locator("#history-refresh").click()
                    page.wait_for_function("document.querySelector('#history-status')?.textContent.includes('5 séries')")
                    self.assert_five(page)
                    self.assertIn((metric, window), requests)
            page.reload(wait_until="domcontentloaded")
            page.wait_for_function("document.querySelector('#history-status')?.textContent.includes('5 séries')")
            self.assert_five(page)
        finally:
            context.close()

    def test_rapid_changes_ignore_obsolete_response(self):
        context, page, requests = self.open_candidate()
        try:
            page.locator("#history-window").select_option("6h")
            page.locator("#history-window").select_option("24h")
            page.locator("#history-metric").select_option("scrape_duration")
            page.locator("#history-window").select_option("1h")
            page.wait_for_function("document.querySelector('#history-status')?.textContent.includes('5 séries')")
            self.assert_five(page)
            self.assertEqual(page.locator("#history-window").input_value(), "1h")
            self.assertIn(("scrape_duration", "1h"), requests)
        finally:
            context.close()

    def test_mobile_layout_and_no_duplicate_legend(self):
        context, page, _ = self.open_candidate(mobile=True)
        try:
            for metric in METRICS:
                page.locator("#history-metric").select_option(metric)
                for window in WINDOWS:
                    page.locator("#history-window").select_option(window)
                    page.wait_for_function("document.querySelector('#history-status')?.textContent.includes('5 séries')")
                    self.assert_five(page)
            self.assertTrue(page.locator("#history-chart").is_visible())
        finally:
            context.close()


if __name__ == "__main__":
    unittest.main()
