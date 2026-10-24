import unittest
from demo.star_capture_identity_plan import plan_capture_identity
from demo.star_legacy_capture_gap_plan import build_gap_plan
from demo.star_capture_execution_worklist import join_capture_plans
from demo.star_browser_capture_tasks import build_browser_capture_tasks
ORIGINS={"n8n":"http://127.0.0.1:5678","glpi":"http://127.0.0.1:8080","grafana":"http://127.0.0.1:3000"}

class BrowserCaptureTasksTest(unittest.TestCase):
    def _work(self, ids=None):
        a=plan_capture_identity("RUN-123", ids or {})
        b=build_gap_plan({"schema":"aiops-legacy-playwright-audit-v1","entries":[]},"RUN-123")
        return join_capture_plans(a,b)
    def test_partial_ready_produces_only_approved_read_only_tasks(self):
        w=self._work({"alert_id":"ALT-123"})
        r=build_browser_capture_tasks(w,{"detect":"http://127.0.0.1:3000/alerts/firing","verify":"http://127.0.0.1:3000/alerts/recovered"},ORIGINS)
        self.assertEqual(len(r["tasks"]),2)
        self.assertFalse(r["browser_executed"])
        self.assertEqual(r["runtime_proof_count"],0)
    def test_no_guessed_urls(self):
        with self.assertRaises(ValueError):
            build_browser_capture_tasks(self._work({"alert_id":"ALT-123"}),{},ORIGINS)
    def test_cross_origin_blocked(self):
        with self.assertRaises(ValueError):
            build_browser_capture_tasks(self._work({"alert_id":"ALT-123"}),{"detect":"http://evil.test/a","verify":"http://127.0.0.1:3000/b"},ORIGINS)
    def test_url_for_missing_identity_blocked(self):
        with self.assertRaises(ValueError):
            build_browser_capture_tasks(self._work(),{"detect":"http://127.0.0.1:3000/a"},ORIGINS)
    def test_duplicate_url_blocked(self):
        with self.assertRaises(ValueError):
            build_browser_capture_tasks(self._work({"alert_id":"ALT-123"}),{"detect":"http://127.0.0.1:3000/a","verify":"http://127.0.0.1:3000/a"},ORIGINS)
if __name__=="__main__":unittest.main()
