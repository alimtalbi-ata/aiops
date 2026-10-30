import unittest

from shared.domain import STAGES, initial_stage_state


class InitialStageStateTests(unittest.TestCase):
    def test_ingest_is_complete_when_run_is_created(self):
        self.assertEqual(initial_stage_state("INGEST"), "PASS")

    def test_worker_stages_remain_pending_until_executed(self):
        for stage in STAGES:
            if stage != "INGEST":
                with self.subTest(stage=stage):
                    self.assertEqual(initial_stage_state(stage), "PENDING")

    def test_stage_order_keeps_ingest_first(self):
        self.assertEqual(STAGES[0], "INGEST")
