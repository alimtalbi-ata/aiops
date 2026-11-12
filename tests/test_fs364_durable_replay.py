"""FS.364 durable replay and contention tests; no GLPI/Temporal side effects."""
import os
import sqlite3
import tempfile
import threading
import unittest
from dataclasses import replace

from app.core.fs364_correlation import Link, ContractRefused, bind

BASE = Link("alert-fs147", "INC-FS147", "RUN-FS147", "EVD-FS147", 147, "DEMO")


def connect(path):
    return sqlite3.connect(path, timeout=10)


def insert(db, link=BASE):
    return bind(db, link, verified_ticket=True, authenticated=True)


class FS364DurabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "links.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_identical_replay_after_restart(self):
        with connect(self.path) as db:
            insert(db)
        with connect(self.path) as db:
            self.assertEqual(insert(db), BASE)
            self.assertEqual(db.execute("SELECT count(*) FROM fs364_links").fetchone()[0], 1)

    def test_conflict_after_restart_preserves_original(self):
        with connect(self.path) as db:
            insert(db)
        with connect(self.path) as db:
            with self.assertRaises(ContractRefused):
                insert(db, replace(BASE, mode="LIVE"))
            self.assertEqual(db.execute("SELECT mode FROM fs364_links").fetchone()[0], "DEMO")

    def test_concurrent_identical_replays_create_one_row(self):
        errors = []
        barrier = threading.Barrier(4)

        def worker():
            try:
                with connect(self.path) as db:
                    barrier.wait(timeout=5)
                    insert(db)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
        self.assertFalse(any(thread.is_alive() for thread in threads), "worker stuck")
        self.assertEqual(errors, [])
        with connect(self.path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM fs364_links").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
