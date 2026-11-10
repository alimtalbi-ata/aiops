"""Checkpoint identities must be unambiguous before opening a transaction."""
import unittest
import test_candidate_core_checkpoint_monotonic as harness_module


class CheckpointStageIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        harness_module.CheckpointMonotonicTests.setUpClass()

    def test_ambiguous_stages_do_not_reach_database(self):
        harness = harness_module.CheckpointMonotonicTests()
        for stage in ('', ' ', ' POLICY', 'POLICY ', 'POLICY\n',
                      'POLICY\t', 'POLICY\x00', 'POLICY\x7f', None, 17):
            with self.subTest(stage=stage):
                _, error, cursor = harness.invoke({'stage': stage, 'version': 1})
                self.assertEqual(error, 422)
                self.assertFalse(cursor.calls)

    def test_canonical_stage_reaches_transaction(self):
        result, error, cursor = harness_module.CheckpointMonotonicTests().invoke(
            {'stage': 'POLICY', 'version': 1, 'workflow_id': 'RUN-1'})
        self.assertIsNone(error)
        self.assertEqual(result, {'run_id': 'RUN-1', 'stage': 'POLICY', 'version': 1})
        self.assertEqual(cursor.calls[0][1], ('RUN-1', 'POLICY', 1, 'RUN-1'))


if __name__ == '__main__':
    unittest.main()
