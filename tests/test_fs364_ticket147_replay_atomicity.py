"""FS364 / ticket 147: durable reference ledger replay and rollback regressions.

SQLite reference only. No GLPI, Temporal, filesystem or host calls.
"""
import sqlite3
import unittest
from dataclasses import replace

from app.core.fs364_correlation import Link, ContractRefused, bind


BASE = Link("fp-lab-92", "INC-LAB-92", "RUN-LAB-92", "EVD-LAB-92", 147, "DEMO")
FLAGS = dict(verified_ticket=True, authenticated=True, stop_auto=True)


class Ticket147ReplayAtomicityTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")

    def tearDown(self):
        self.db.close()

    def rows(self):
        return self.db.execute(
            "SELECT fingerprint, incident_id, run_id, evidence_id, ticket_id, mode "
            "FROM fs364_links ORDER BY fingerprint"
        ).fetchall()

    def test_identical_retry_keeps_one_row(self):
        bind(self.db, BASE, **FLAGS)
        first = self.rows()
        self.assertEqual(bind(self.db, BASE, **FLAGS), BASE)
        self.assertEqual(self.rows(), first)
        self.assertEqual(len(first), 1)

    def test_conflicting_fingerprint_retry_rolls_back(self):
        bind(self.db, BASE, **FLAGS)
        first = self.rows()
        with self.assertRaises(ContractRefused):
            bind(self.db, replace(BASE, evidence_id="EVD-other"), **FLAGS)
        self.assertEqual(self.rows(), first)

    def test_reusing_run_with_new_fingerprint_is_refused(self):
        bind(self.db, BASE, **FLAGS)
        first = self.rows()
        with self.assertRaises(ContractRefused):
            bind(self.db, replace(BASE, fingerprint="fp-other",
                                  incident_id="INC-other", evidence_id="EVD-other"), **FLAGS)
        self.assertEqual(self.rows(), first)

    def test_refused_authentication_does_not_write(self):
        bind(self.db, BASE, **FLAGS)
        first = self.rows()
        for bad in ("true", 1, None, False):
            with self.subTest(bad=bad):
                with self.assertRaises(ContractRefused):
                    bind(self.db, replace(BASE, fingerprint="fp-other",
                                          incident_id="INC-other", run_id="RUN-other",
                                          evidence_id="EVD-other"),
                         verified_ticket=True, authenticated=bad, stop_auto=True)
                self.assertEqual(self.rows(), first)


if __name__ == "__main__":
    unittest.main()
