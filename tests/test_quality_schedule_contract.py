from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/quality.yml").read_text()


class QualityScheduleContractTests(unittest.TestCase):
    def test_daily_utc_schedule_is_present(self):
        self.assertIn('    - cron: "23 2 * * *"', WORKFLOW)

    def test_manual_dispatch_is_available(self):
        self.assertIn("  workflow_dispatch:", WORKFLOW)

    def test_quality_workflow_remains_hosted_and_read_only(self):
        self.assertIn("policy-and-static:\n    runs-on: ubuntu-24.04", WORKFLOW)
        self.assertIn("permissions:\n  contents: read", WORKFLOW)
        self.assertNotIn("self-hosted", WORKFLOW)

    def test_all_three_jobs_checkout_and_verify_exact_source_head(self):
        # A green PR synthetic merge commit is not D0 exact-head evidence.
        expr = 'ref: ${{ github.event.pull_request.head.sha || github.sha }}'
        expected = 'AIOPS_EXPECTED_HEAD_SHA: ${{ github.event.pull_request.head.sha || github.sha }}'
        guard = 'run: test "$(git rev-parse HEAD)" = "$AIOPS_EXPECTED_HEAD_SHA"'
        self.assertEqual(WORKFLOW.count(expr), 3)
        self.assertEqual(WORKFLOW.count(expected), 3)
        self.assertEqual(WORKFLOW.count(guard), 3)
        self.assertEqual(WORKFLOW.count("persist-credentials: false"), 3)


if __name__ == "__main__":
    unittest.main()
