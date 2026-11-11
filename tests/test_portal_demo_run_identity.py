import pathlib
import unittest

from app.portal.demo_run_identity import matches_demo_run


class DemoRunIdentityTests(unittest.TestCase):
    def test_each_route_checks_its_own_selected_identity(self):
        source = (pathlib.Path(__file__).resolve().parents[1] / "app/portal/main.py").read_text()
        timeline = source.split('@app.get("/timeline"', 1)[1].split('@app.get("/twin"', 1)[0]
        demo = source.split('@app.get("/demo-studio/run/{rid}"', 1)[1].split('@app.get("/api/demo-status/{rid}"', 1)[0]
        status = source.split('@app.get("/api/demo-status/{rid}"', 1)[1].split('@app.get("/qualification"', 1)[0]
        self.assertIn('matches_demo_run(detail,selected,match.get("mode"))', timeline)
        self.assertNotIn('matched.get("mode")', timeline)
        self.assertIn('matches_demo_run(detail,rid,matched.get("mode"))', demo)
        self.assertIn('matches_demo_run(detail,rid,allowed.get("mode"))', status)

    def test_valid_flat_and_nested_envelopes(self):
        for data in (
            {"run_id": "RUN-1", "mode": "DEMO", "status": "BLOCKED"},
            {"run": {"run_id": "RUN-1", "mode": "DEMO", "status": "BLOCKED"}},
            {"run": {"status": "BLOCKED"}, "events": []},
            {"run_id": "RUN-1", "status": "BLOCKED"},
            {"run_id": "RUN-1", "run": {"run_id": "RUN-1", "mode": "DEMO"}},
        ):
            with self.subTest(data=data):
                self.assertTrue(matches_demo_run(data, "RUN-1", "DEMO"))

    def test_reject_cross_run_cross_mode_and_unverified(self):
        for data in (
            None, {},
            {"run_id": "RUN-2", "mode": "DEMO"},
            {"run_id": "RUN-1", "mode": "LIVE"},
            {"run_id": "RUN-2", "run": {"run_id": "RUN-1", "mode": "DEMO"}},

            {"run": None}, {"run": "bad"},
        ):
            with self.subTest(data=data):
                self.assertFalse(matches_demo_run(data, "RUN-1", "DEMO"))


if __name__ == "__main__":
    unittest.main()
