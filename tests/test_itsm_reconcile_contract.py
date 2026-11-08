"""Offline regression matrix for FS1250/FS147 reconciliation. No external effects."""
import unittest
from dataclasses import replace
from app.core.itsm_reconcile_contract import Candidate, Snapshot, Status, classify

class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.c = Candidate("GLPI", "201", "tenant", "INC-1250",
                           "RUN-8CA56A39E58944F1", True)
        self.s = Snapshot("tenant", "INC-1250", "RUN-8CA56A39E58944F1",
                          "DEMO", True, False, None, (self.c,))

    def test_existing_unlinked(self):
        self.assertEqual(classify(self.s), Status.EXISTING_UNLINKED)

    def test_existing_fs147(self):
        self.assertEqual(classify(replace(self.s, xref_ticket_id="147",
                         candidates=(replace(self.c, ticket_id="147"),))), Status.MATCHED)

    def test_ui_not_authoritative(self):
        self.assertEqual(classify(replace(self.s, candidates=(
            replace(self.c, readback_verified=False),))), Status.UNKNOWN)

    def test_missing_xref_not_missing_ticket(self):
        self.assertEqual(classify(replace(self.s, candidates=())), Status.UNKNOWN)

    def test_complete_inventory_missing(self):
        self.assertEqual(classify(replace(self.s, candidates=(),
                         inventory_complete=True)), Status.MISSING)

    def test_duplicate_candidates(self):
        self.assertEqual(classify(replace(self.s, candidates=(
            self.c, replace(self.c, ticket_id="202")))), Status.AMBIGUOUS)

    def test_conflicting_xref(self):
        self.assertEqual(classify(replace(self.s, xref_ticket_id="200")), Status.CONFLICT)

    def test_live_denied(self):
        self.assertEqual(classify(replace(self.s, mode="LIVE")), Status.NOT_ELIGIBLE)

    def test_unknown_mode(self):
        self.assertEqual(classify(replace(self.s, mode="OTHER")), Status.UNKNOWN)

    def test_wrong_run(self):
        self.assertEqual(classify(replace(self.s, run_id="OTHER")), Status.UNKNOWN)

    def test_wrong_tenant(self):
        self.assertEqual(classify(replace(self.s, tenant_id="other")), Status.UNKNOWN)

    def test_malformed(self):
        self.assertEqual(classify(None), Status.UNKNOWN)
        self.assertEqual(classify(replace(self.s, candidates=[])), Status.UNKNOWN)

    def test_pure_repeat(self):
        self.assertEqual(classify(self.s), classify(self.s))
        self.assertIsNone(self.s.xref_ticket_id)

if __name__ == "__main__":
    unittest.main()
