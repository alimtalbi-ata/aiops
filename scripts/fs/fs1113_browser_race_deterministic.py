#!/usr/bin/env python3
"""Deterministic Chromium regression for FS1113, against isolated candidate only.

Run after FS1107 has started the candidate at 127.0.0.1:17898.
This test deliberately simulates a transport that ignores AbortSignal, proving
the request-generation guard rather than merely observing an aborted fetch.
"""
import json
import os
from playwright.sync_api import sync_playwright

BASE = os.environ.get("FS1113_CANDIDATE_URL", "http://127.0.0.1:17898").rstrip("/")
assert BASE.startswith("http://127.0.0.1:") or BASE.startswith("http://localhost:"), "isolated candidate required"

INJECT = r"""
(() => {
  const nativeFetch = window.fetch.bind(window);
  let seq = 0;
  const makeSeries = (marker) => Array.from({length:5}, (_, i) => ({
    job: 'fs1113-' + marker, instance: 'target-' + i,
    points: [[1700000000, i + 1], [1700000060, i + 2]]
  }));
  window.fetch = (url, options) => {
    const u = new URL(String(url), location.href);
    if (u.pathname !== '/api/fs1089/prometheus/history')
      return nativeFetch(url, options);
    const metric = u.searchParams.get('metric');
    const windowSize = u.searchParams.get('window');
    const order = ++seq;
    // First response resolves AFTER the second even if its signal was aborted.
    const delay = order === 1 ? 1400 : 30;
    return new Promise(resolve => setTimeout(() => resolve(new Response(
      JSON.stringify({metric, window:windowSize, series:makeSeries(metric + '-' + windowSize),
                      step_seconds:60}),
      {status:200, headers:{'Content-Type':'application/json'}}
    )), delay));
  };
})();
"""

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path="/usr/bin/chromium",
                                    args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            # Exercise both Prometheus metrics and all three supported windows.
            # Each fresh page starts with a deliberately slow 1h request.
            for metric in ("availability", "scrape_duration"):
                for window_size in ("1h", "6h", "24h"):
                    page = browser.new_page()
                    try:
                        page.add_init_script(INJECT)
                        response = page.goto(BASE + "/explorer/visual", wait_until="domcontentloaded", timeout=25000)
                        assert response and response.status == 200, "candidate visual endpoint unavailable"
                        # Force at least one newer request even for the default 1h/availability case.
                        if metric != "availability":
                            page.locator("#history-metric").select_option(metric)
                        if window_size == "1h":
                            page.locator("#history-window").select_option("6h")
                        page.locator("#history-window").select_option(window_size)
                        page.wait_for_function("""([m, w]) => {
                          const s=document.querySelector('#history-status')?.textContent || '';
                          return s.endsWith(' · ' + w) && s.includes('points') &&
                                 !document.querySelector('#history-refresh').disabled &&
                                 document.querySelector('#history-metric').value === m;
                        }""", arg=[metric, window_size], timeout=10000)
                        page.wait_for_timeout(1600)  # stale first response resolves after the latest
                        assert page.locator("#history-legend > span").count() == 5, (metric, window_size)
                        assert page.locator("#history-chart path").count() == 5, (metric, window_size)
                        labels = page.locator("#history-legend > span").all_inner_texts()
                        assert all("fs1113-" + metric + "-" + window_size in item for item in labels), (metric, window_size, labels)
                        assert page.locator("#history-status").inner_text().endswith(" · " + window_size)
                        print(f"FS1113_DETERMINISTIC_STALE_RESPONSE=PASS metric={metric} window={window_size}")
                    finally:
                        page.close()
        finally:
            browser.close()

if __name__ == "__main__":
    main()
