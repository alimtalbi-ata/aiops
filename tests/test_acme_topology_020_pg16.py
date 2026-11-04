"""Disposable PG16 regression for additive migration 020; no LIVE/host effects."""
from pathlib import Path
import unittest
from urllib.parse import urlsplit, urlunsplit
import os

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_001 = (ROOT / "db/migrations/001_schema.sql").read_text()
MIGRATION_019 = (ROOT / "db/migrations/019_acme_sandbox_twin_topology.sql").read_text()
MIGRATION_020 = (ROOT / "db/migrations/020_acme_sandbox_twin_provenance_fence.sql").read_text()
NODE = "ACME-TEST-SAN-ARRAY-DELL-01"
EDGE = "ACME-TEST-SIM-EDGE-001"


class ACME019ReplayFencePG16(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = os.environ["DATABASE_URL"]
        parsed = urlsplit(cls.original)
        cls.name = "aiops_acme_019_fence_ci"
        cls.url = urlunsplit((parsed.scheme, parsed.netloc, "/" + cls.name, "", ""))
        with psycopg.connect(cls.original, autocommit=True) as admin:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(cls.name)))
        try:
            with psycopg.connect(cls.url) as conn:
                conn.execute(MIGRATION_001)
                conn.execute(MIGRATION_019)
                conn.execute(MIGRATION_020)
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        with psycopg.connect(cls.original, autocommit=True) as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (cls.name,))
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(
                sql.Identifier(cls.name)))

    def assert_rejected(self, statements, marker, replay_019=False):
        # Each test has its own transaction: deliberate corruption is rolled back.
        with psycopg.connect(self.url) as conn:
            for statement, params in statements:
                conn.execute(statement, params)
            if replay_019:
                # 019's original narrow check succeeds; 020 must reject it.
                conn.execute(MIGRATION_019)
            with self.assertRaises(psycopg.Error) as caught:
                conn.execute(MIGRATION_020)
            self.assertIn(marker, str(caught.exception))
            conn.rollback()
        with psycopg.connect(self.url) as conn:
            conn.execute(MIGRATION_020)  # Baseline still qualifies after rollback.

    def test_01_exact_nine_eight_and_idempotent_replay(self):
        with psycopg.connect(self.url) as conn:
            for _ in range(3):
                conn.execute(MIGRATION_020)
            self.assertEqual(conn.execute(
                "SELECT count(*) FROM aiops.twin_nodes "
                "WHERE node_id LIKE 'ACME-TEST-%'").fetchone()[0], 9)
            self.assertEqual(conn.execute(
                "SELECT count(*) FROM aiops.twin_edges "
                "WHERE edge_id LIKE 'ACME-TEST-%'").fetchone()[0], 8)

    def test_02_existing_node_metadata_collision_rejected_after_019_replay(self):
        for column, value in (
            ("name", "foreign Dell array"),
            ("criticality", 4),
            ("confidence", 0.5),
            ("valid_from", None),
            ("valid_to", "2026-11-03T00:00:00Z"),
        ):
            with self.subTest(column=column):
                self.assert_rejected(
                    [(f"UPDATE aiops.twin_nodes SET {column}=%s WHERE node_id=%s",
                      (value, NODE))],
                    "acme_sandbox_twin_node_provenance_conflict",
                    replay_019=True)

    def test_03_existing_edge_metadata_collision_rejected_after_019_replay(self):
        for column, value in (
            ("redundancy", 2),
            ("confidence", 0.4),
            ("valid_from", None),
            ("valid_to", "2026-11-03T00:00:00Z"),
        ):
            with self.subTest(column=column):
                self.assert_rejected(
                    [(f"UPDATE aiops.twin_edges SET {column}=%s WHERE edge_id=%s",
                      (value, EDGE))],
                    "acme_sandbox_twin_edge_provenance_conflict",
                    replay_019=True)

    def test_04_extra_site_node_and_foreign_inbound_edge_rejected(self):
        self.assert_rejected(
            [("INSERT INTO aiops.twin_nodes "
              "(node_id,type,name,site,state,criticality,confidence,valid_from) "
              "VALUES ('FOREIGN-IN-SIM-SITE','STORAGE','foreign','ACME-TEST-SIMULATION',"
              "'SIMULATED',5,1,now())", ())],
            "acme_sandbox_twin_node_provenance_conflict")
        self.assert_rejected(
            [("INSERT INTO aiops.twin_nodes "
              "(node_id,type,name,site,state) "
              "VALUES ('FOREIGN-LIVE-ARRAY','STORAGE','live','PARIS','HEALTHY')", ()),
             ("INSERT INTO aiops.twin_edges "
              "(edge_id,source_id,target_id,relation_type,confidence) "
              "VALUES ('FOREIGN-INBOUND','FOREIGN-LIVE-ARRAY',%s,'REAL_DEPENDS_ON',1)",
              (NODE,))],
            "acme_sandbox_twin_edge_provenance_conflict")

    def test_05_acme_edge_id_with_foreign_endpoints_rejected(self):
        self.assert_rejected(
            [("INSERT INTO aiops.twin_nodes (node_id,type,name,site,state) "
              "VALUES ('FOREIGN-LEFT','STORAGE','left','PARIS','HEALTHY'),"
              "('FOREIGN-RIGHT','STORAGE','right','PARIS','HEALTHY')", ()),
             ("INSERT INTO aiops.twin_edges "
              "(edge_id,source_id,target_id,relation_type,confidence) "
              "VALUES ('ACME-TEST-SIM-EDGE-009','FOREIGN-LEFT',"
              "'FOREIGN-RIGHT','REAL_DEPENDS_ON',1)", ())],
            "acme_sandbox_twin_edge_provenance_conflict")

    def test_06_unrelated_foreign_graph_is_not_rejected(self):
        with psycopg.connect(self.url) as conn:
            conn.execute(
                "INSERT INTO aiops.twin_nodes (node_id,type,name,site,state) "
                "VALUES ('FOREIGN-LEFT','STORAGE','left','PARIS','HEALTHY'),"
                "('FOREIGN-RIGHT','STORAGE','right','PARIS','HEALTHY')")
            conn.execute(
                "INSERT INTO aiops.twin_edges "
                "(edge_id,source_id,target_id,relation_type,confidence) "
                "VALUES ('FOREIGN-EDGE','FOREIGN-LEFT','FOREIGN-RIGHT','PATH',1)")
            conn.execute(MIGRATION_020)
            conn.rollback()

    def test_07_read_only_fence_never_changes_graph(self):
        with psycopg.connect(self.url) as conn:
            before_nodes = conn.execute(
                "SELECT * FROM aiops.twin_nodes ORDER BY node_id").fetchall()
            before_edges = conn.execute(
                "SELECT * FROM aiops.twin_edges ORDER BY edge_id").fetchall()
            conn.execute(MIGRATION_020)
            self.assertEqual(before_nodes, conn.execute(
                "SELECT * FROM aiops.twin_nodes ORDER BY node_id").fetchall())
            self.assertEqual(before_edges, conn.execute(
                "SELECT * FROM aiops.twin_edges ORDER BY edge_id").fetchall())


if __name__ == "__main__":
    unittest.main()
