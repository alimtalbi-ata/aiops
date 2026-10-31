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


if __name__ == "__main__":
    unittest.main()
