"""Offline capture contract + real Chromium against a disposable local fixture."""
import json
import tempfile
import threading
import unittest
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from demo.star_snapshot_browser import CapturePlan, capture, validate_plan, _safe_url

RUN = "RUN-STAR-ACME-001"
CORR = "CORR-STAR-ACME-001"

class FixtureHandler(BaseHTTPRequestHandler):
    requests = []
    def do_GET(self):
        self.__class__.requests.append(("GET", self.path))
        body = f'''<!doctype html><html><body>
        <div id="run">{RUN}</div><div id="correlation">{CORR}</div><div id="event">EXEC-77</div>
        <div id="state">completed</div><div id="secret">private-user@invalid.example</div>
        <div style="height:500px">Fixture, not production.</div>
        </body></html>'''.encode()
        if self.path == "/executions/EXEC-77":
            self.send_response(200);self.send_header("Content-Type","text/html");self.end_headers();self.wfile.write(body)
        else:
            self.send_response(404);self.end_headers()
    def log_message(self,*args): pass

FIXTURE_HTML = f'''<!doctype html><html><body><div id="run">{RUN}</div><div id="correlation">{CORR}</div><div id="event">EXEC-77</div><div id="state">completed</div><div id="secret">private-user@invalid.example</div><div style="height:500px">Isolated fixture, not runtime.</div></body></html>'''

class BrowserContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.origin = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join(timeout=2)

    def plan(self):
        return CapturePlan("correlate", RUN, CORR, "EXEC-77", self.origin+"/executions/EXEC-77",
                           "completed", "#run", "#event", "#state", ("#secret",),
                           self.origin, "ISOLATED_TEST_FIXTURE", "#correlation")

    def test_dry_run_zero_requests(self):
        FixtureHandler.requests.clear()
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(capture(self.plan(), Path(td))["result"], "DRY_RUN")
            self.assertEqual(list(Path(td).iterdir()), [])
        self.assertEqual(FixtureHandler.requests, [])

    def test_wrong_identity_and_origin_refused(self):
        p=self.plan()
        for change in (dict(run_id=""),dict(correlation_id=""),dict(correlation_selector=""),dict(event_ref="DIFFERENT"),
                       dict(url="http://127.0.0.1:9000/executions/EXEC-77"),
                       dict(url=self.origin+"/executions/EXEC-77?token=abc"),
                       dict(url=self.origin+"/executions/EXEC-77#x"),
                       dict(expected_state="approved"),dict(redact_selectors=()),
                       dict(environment="REAL_PROOF")):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_plan(replace(p,**change))

    def test_glpi_v1_deep_link(self):
        p=replace(self.plan(), cue="ticket", event_ref="441", expected_state="open",
                  url="http://127.0.0.1:8080/front/ticket.form.php?id=441",
                  allowed_origin="http://127.0.0.1:8080")
        self.assertEqual(validate_plan(p)["service"],"glpi")
        for url in ("http://127.0.0.1:18080/front/ticket.form.php?id=441",
                    "http://127.0.0.1:8080/front/ticket.form.php?id=442"):
            with self.assertRaises(ValueError): validate_plan(replace(p,url=url,allowed_origin=url.split('/front')[0]))

    def test_redaction_url_removes_id_query(self):
        self.assertNotIn("token",_safe_url("http://127.0.0.1:8080/front/ticket.form.php?id=441&token=abc","441"))
        self.assertNotIn("EXEC-77",_safe_url(self.plan().url,"EXEC-77"))

    def test_real_chromium_fixture_capture(self):
        with tempfile.TemporaryDirectory() as td:
            result=capture(self.plan(),Path(td),approved_read=True,fixture_html=FIXTURE_HTML)
            self.assertEqual(result["result"],"CAPTURED_UNREVIEWED")
            manifest=json.loads((Path(td)/result["manifest"]).read_text())
            self.assertEqual(manifest["provenance"],"ISOLATED_TEST_FIXTURE", "#correlation")
            self.assertFalse(manifest["runtime_page_authenticated"])
            self.assertFalse(manifest["business_outcome_verified"])
            self.assertEqual(manifest["expected_state"],manifest["observed_state"])
            import hashlib
            self.assertEqual(hashlib.sha256((Path(td)/manifest["screenshot_file"]).read_bytes()).hexdigest(),manifest["sha256"])
            with self.assertRaises(ValueError): capture(self.plan(),Path(td),approved_read=True,fixture_html=FIXTURE_HTML)

    def test_grafana_uid_exact_deep_link(self):
        p=replace(self.plan(), cue="detect", event_ref="dashboardABC", expected_state="firing",
                  url=self.origin+"/d/dashboardABC/acme")
        self.assertEqual(validate_plan(p)["service"],"grafana")
        with self.assertRaises(ValueError):
            validate_plan(replace(p,url=self.origin+"/d/wrong/dashboardABC"))

    def test_visible_password_login_overlay_rejected_even_with_matching_proof(self):
        # F20.13 historical PASS reports included actual login screens.
        # Valid-looking run/correlation/event DOM must not override login UI.
        html = FIXTURE_HTML.replace(
            "</body>", '<form action="/login"><input type="password" /></form></body>'
        )
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, "login surface"):
                capture(self.plan(), Path(td), approved_read=True, fixture_html=html)
            self.assertEqual(list(Path(td).iterdir()), [])

    def test_visible_signin_form_without_password_rejected(self):
        html = FIXTURE_HTML.replace(
            "</body>", '<form action="/signin"><input name="username" /></form></body>'
        )
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, "login surface"):
                capture(self.plan(), Path(td), approved_read=True, fixture_html=html)
            self.assertEqual(list(Path(td).iterdir()), [])

    def test_hidden_password_widget_does_not_invalidate_event_view(self):
        html = FIXTURE_HTML.replace(
            "</body>", '<form action="/login" style="display:none"><input type="password" /></form></body>'
        )
        with tempfile.TemporaryDirectory() as td:
            result = capture(self.plan(), Path(td), approved_read=True, fixture_html=html)
            self.assertEqual(result["result"], "CAPTURED_UNREVIEWED")
            manifest = json.loads((Path(td) / result["manifest"]).read_text())
            self.assertFalse(manifest["runtime_page_authenticated"])

    def test_js_error_fails_closed(self):
        html = FIXTURE_HTML.replace("</body>", "<script>throw new Error('fixture error')</script></body>")
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                capture(self.plan(), Path(td), approved_read=True, fixture_html=html)
            self.assertEqual(list(Path(td).iterdir()), [])

    def test_post_request_fails_closed(self):
        html = FIXTURE_HTML.replace("</body>",
            f'<script>fetch("{self.origin}/api/mutate", {{method:"POST"}}).catch(()=>{{}});</script></body>')
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                capture(self.plan(), Path(td), approved_read=True, fixture_html=html)
            self.assertEqual(list(Path(td).iterdir()), [])

    def test_cross_origin_request_fails_closed(self):
        html = FIXTURE_HTML.replace("</body>", '<img src="https://example.invalid/telemetry" /></body>')
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                capture(self.plan(), Path(td), approved_read=True, fixture_html=html)
            self.assertEqual(list(Path(td).iterdir()), [])

    def test_fixture_cannot_be_used_for_operator_runtime(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                capture(replace(self.plan(), environment="OPERATOR_BROWSER_UNREVIEWED"),
                        Path(td), approved_read=True, fixture_html=FIXTURE_HTML)

    def test_missing_mask_fails_without_output(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                capture(replace(self.plan(),redact_selectors=("#missing",)),Path(td),approved_read=True,fixture_html=FIXTURE_HTML)
            self.assertEqual(list(Path(td).iterdir()),[])

    def test_substring_run_id_and_execution_id_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            for change in (dict(run_id="RUN-STAR-ACME-00"), dict(event_ref="EXEC-7")):
                with self.subTest(change=change), self.assertRaises(ValueError):
                    capture(replace(self.plan(), **change), Path(td), approved_read=True,
                            fixture_html=FIXTURE_HTML)
            self.assertEqual(list(Path(td).iterdir()), [])

    def test_fixture_network_get_is_blocked_even_on_allowlisted_origin(self):
        html = FIXTURE_HTML.replace("</body>",
            f'<script>fetch("{self.origin}/executions/EXEC-77").catch(()=>{{}});</script></body>')
        FixtureHandler.requests.clear()
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                capture(self.plan(), Path(td), approved_read=True, fixture_html=html)
            self.assertEqual(list(Path(td).iterdir()), [])
        self.assertEqual(FixtureHandler.requests, [])

    def test_ci_offline_fence_blocks_runtime_even_with_capture_flag(self):
        from unittest.mock import patch
        with patch.dict("os.environ", {"AIOPS_STAR_NO_RUNTIME": "1"}):
            with tempfile.TemporaryDirectory() as td:
                with self.assertRaisesRegex(ValueError, "runtime browsing disabled"):
                    capture(self.plan(), Path(td), approved_read=True)
                self.assertEqual(list(Path(td).iterdir()), [])

    def test_grafana_fixed_window_rejects_cross_run_and_relative_times(self):
        p = replace(self.plan(), cue="detect", event_ref="dashboardABC",
                    expected_state="firing", url=self.origin+"/d/dashboardABC/acme")
        with self.assertRaisesRegex(ValueError, "fixed event window"):
            validate_plan(replace(p, environment="OPERATOR_BROWSER_UNREVIEWED"))
        valid = self.origin + "/d/dashboardABC/acme?from=1792746000000&to=1792746060000&var-run_id=" + RUN
        self.assertEqual(validate_plan(replace(p, url=valid, environment="OPERATOR_BROWSER_UNREVIEWED"))["service"], "grafana")
        for url in (valid.replace(RUN, "RUN-OTHER-999"), valid.replace("1792746000000", "now-5m"),
                    valid.replace("1792746060000", "1792756060000"), valid + "&token=secret"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_plan(replace(p, url=url, environment="OPERATOR_BROWSER_UNREVIEWED"))

    def test_correlated_identity_is_verified_not_merely_recorded(self):
        with tempfile.TemporaryDirectory() as td:
            for change in (dict(correlation_id="CORR-OTHER-999"),
                           dict(correlation_selector="#missing")):
                with self.subTest(change=change), self.assertRaises(ValueError):
                    capture(replace(self.plan(), **change), Path(td),
                            approved_read=True, fixture_html=FIXTURE_HTML)
            self.assertEqual(list(Path(td).iterdir()), [])

    def test_redacted_url_never_leaks_unrelated_path_identifiers(self):
        private = "RUN-SECRET-UNRELATED"
        cases = (
            (f"http://localhost:5678/workflow/{private}/executions/EXEC-77", "EXEC-77"),
            (f"http://localhost:3000/d/dashboardABC/{private}", "dashboardABC"),
            (f"http://localhost:8080/front/ticket.form.php?id=441&secret={private}", "441"),
        )
        for url, event in cases:
            with self.subTest(url=url):
                redacted = _safe_url(url, event)
                self.assertNotIn(private, redacted)
                self.assertNotIn(event, redacted)
                self.assertNotIn("localhost", redacted)

    def test_missing_dom_identity_fails_without_output(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                capture(replace(self.plan(),run_id="RUN-ANOTHER-999"),Path(td),approved_read=True,fixture_html=FIXTURE_HTML)
            self.assertEqual(list(Path(td).iterdir()),[])

if __name__=="__main__": unittest.main()
