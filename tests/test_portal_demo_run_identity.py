import unittest

from app.portal.demo_run_identity import matches_demo_run


class DemoRunIdentityTests(unittest.TestCase):
    def test_valid_flat_and_nested_envelopes(self):
        for data in (
            {"run_id": "RUN-1", "mode": "DEMO", "status": "BLOCKED"},
            {"run": {"run_id": "RUN-1", "mode": "DEMO", "status": "BLOCKED"}},
            {"run_id": "RUN-1", "run": {"run_id": "RUN-1", "mode": "DEMO"}},
        ):
            with self.subTest(data=data):
                self.assertTrue(matches_demo_run(data, "RUN-1", "DEMO"))

    def test_reject_cross_run_cross_mode_and_unverified(self):
        for data in (
            None, {}, {"status": "RESOLVED"},
            {"run_id": "RUN-2", "mode": "DEMO"},
            {"run_id": "RUN-1", "mode": "LIVE"},
            {"run_id": "RUN-2", "run": {"run_id": "RUN-1", "mode": "DEMO"}},
            {"run": {"run_id": "RUN-1"}},
            {"run": None}, {"run": "bad"},
        ):
            with self.subTest(data=data):
                self.assertFalse(matches_demo_run(data, "RUN-1", "DEMO"))


if __name__ == "__main__":
    unittest.main()
