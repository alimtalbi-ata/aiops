import unittest

from app.portal.runs_display import MAX_COCKPIT_RUNS, cockpit_runs_projection


class RunsDisplayContract(unittest.TestCase):
    def test_critical_sixteenth_run_is_visible(self):
        runs = [{"run_id": f"RUN-{i:03d}", "status": "FAILED" if i == 16 else "UNKNOWN"} for i in range(1, 18)]
        rows, omitted = cockpit_runs_projection(runs)
        self.assertEqual(len(rows), 17)
        self.assertEqual(rows[15][0], "RUN-016")
        self.assertEqual(rows[15][2], "FAILED")
        self.assertEqual(omitted, 0)

    def test_boundary_and_overflow_are_explicit(self):
        for count in (0, 15, 100, 101, 117):
            with self.subTest(count=count):
                rows, omitted = cockpit_runs_projection([{"run_id": f"RUN-{i}"} for i in range(count)])
                self.assertEqual(len(rows), min(count, MAX_COCKPIT_RUNS))
                self.assertEqual(omitted, max(0, count - MAX_COCKPIT_RUNS))

    def test_malformed_envelope_is_rejected(self):
        for value in (None, {}, "secret", [None], [{"run_id": "OK"}, "bad"]):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    cockpit_runs_projection(value)

    def test_missing_fields_are_unknown_not_success(self):
        self.assertEqual(cockpit_runs_projection([{}]), ([("UNKNOWN",) * 4], 0))


if __name__ == "__main__":
    unittest.main()
