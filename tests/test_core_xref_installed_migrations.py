"""Core xref installed 009-012 migration gate (DEV / disposable PostgreSQL 16 only).

This test reads the actual db/migrations files, never tests/fixtures copies.
It does not apply migrations to the existing Core CI database.
"""
import hashlib
import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import unittest

ROOT = Path(__file__).resolve().parent.parent
MIG = ROOT / "db" / "migrations"
PINNED_BLOBS = {
    "009_ai_decision_ledger.sql": "bfed91982654b6baf0026408fa5134a22af421bb",
    "010_evidence_identity.sql": "1ddafd94639af60ce38b6df0acafd7f63d6b4af2",
    "011_hitl_decision_outbox.sql": "b096af57cb19b9618e3d7d4d68a8ef3d56890934",
    "012_itsm_xref_read.sql": "9408dcf9d92d5bfbdb75968a5a0b0a55f2985457",
}
ORDER = (
    "001_schema.sql",
    "004_operational_model.sql",
    *PINNED_BLOBS,
)


def _git_blob_sha(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


class InstalledMigrationContract(unittest.TestCase):
    def test_installed_git_provenance_and_unique_ordinals(self):
        files = list(MIG.glob("[0-9][0-9][0-9]_*.sql"))
        ordinals = [p.name[:3] for p in files]
        self.assertEqual(len(ordinals), len(set(ordinals)), "duplicate migration ordinal")
        for name, sha in PINNED_BLOBS.items():
            with self.subTest(name=name):
                self.assertEqual(_git_blob_sha((MIG / name).read_bytes()), sha)
                self.assertEqual(sum(p.name[:3] == name[:3] for p in files), 1)
        self.assertFalse((MIG / "009_itsm_xref_read.sql").exists(),
                         "historical xref 009 conflicts with AI 009")
        self.assertEqual([n[:3] for n in ORDER[-4:]], ["009", "010", "011", "012"])

    def test_expected_integrity_and_immutability_guards_present(self):
        sql = {name: (MIG / name).read_text(encoding="utf-8").lower()
               for name in PINNED_BLOBS}
        self.assertIn("reject_immutable_mutation", sql["009_ai_decision_ledger.sql"])
        self.assertIn("unique index if not exists ux_evidence_source_payload_hash",
                      sql["010_evidence_identity.sql"])
        self.assertIn("hitl_decision_outbox", sql["011_hitl_decision_outbox.sql"])
        xref = sql["012_itsm_xref_read.sql"]
        for fragment in ("tenant_resource_ownership", "itsm_xref_events",
                         "source_event_id", "association_id",
                         "authenticated_id_readback", "authenticated_source_api",
                         "prevent_itsm_xref_mutation", "trg_itsm_owner_immutable",
                         "trg_itsm_xref_immutable"):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, xref)


@unittest.skipUnless(os.environ.get("AIOPS_XREF_CI_DISPOSABLE") == "1"
                     and os.environ.get("GITHUB_ACTIONS") == "true",
                     "GitHub Actions disposable PostgreSQL 16 only")
class InstalledMigrationPostgres16(unittest.TestCase):
    def test_transactional_rollback_idempotence_and_immutable_ownership(self):
        import psycopg
        from psycopg import sql as psql

        raw_url = os.environ["DATABASE_URL"]
        parsed = urlsplit(raw_url)
        if (parsed.scheme not in ("postgresql", "postgres")
                or parsed.hostname != "127.0.0.1"
                or parsed.port != 5432
                or parsed.path != "/aiops"
                or parsed.username != "aiops"
                or parsed.query or parsed.fragment):
            raise RuntimeError("Refusing non-disposable/non-loopback PostgreSQL target")
        scripts = [(name, (MIG / name).read_text(encoding="utf-8"))
                   for name in ORDER]
        database_name = "aiops_xref_installed_ci"
        isolated_url = urlunsplit((parsed.scheme, parsed.netloc,
                                   "/" + database_name, "", ""))
        created = False
        with psycopg.connect(raw_url, autocommit=True) as admin:
            version = int(admin.execute("show server_version_num").fetchone()[0])
            self.assertTrue(160000 <= version < 170000,
                            "requires PostgreSQL 16")
            # CREATE fails if DB already exists; never overwrite an unknown DB.
            admin.execute(psql.SQL("CREATE DATABASE {}").format(
                psql.Identifier(database_name)))
            created = True
        try:
            with psycopg.connect(isolated_url) as conn:
                for name, body in scripts:
                    with self.subTest(stage="transactional_trial", migration=name):
                        conn.execute(body)
                self.assertIsNotNone(conn.execute(
                    "select to_regclass('aiops.itsm_xref_events')").fetchone()[0])
                conn.rollback()
            with psycopg.connect(isolated_url) as conn:
                for table in ("analysis_records", "hitl_decision_outbox",
                              "itsm_xref_events", "tenant_resource_ownership"):
                    self.assertIsNone(conn.execute(
                        "select to_regclass(%s)", ("aiops." + table,)).fetchone()[0])
            table_counts = []
            for iteration in (1, 2):
                with psycopg.connect(isolated_url) as conn:
                    for name, body in scripts:
                        with self.subTest(stage="idempotence",
                                          iteration=iteration, migration=name):
                            conn.execute(body)
                    table_counts.append(conn.execute(
                        "select count(*) from information_schema.tables "
                        "where table_schema='aiops'").fetchone()[0])
            self.assertEqual(table_counts[0], table_counts[1])
            with psycopg.connect(isolated_url) as conn:
                for table in ("analysis_records", "hitl_decision_outbox",
                              "itsm_xref_events", "tenant_resource_ownership"):
                    self.assertIsNotNone(conn.execute(
                        "select to_regclass(%s)", ("aiops." + table,)).fetchone()[0])
                # Core REJECT-only claim/ACK SQL: parse and plan against the
                # installed 009-012 schema, not fixture copies. EXPLAIN is
                # read-only; populated delivery and downgrade remain separate.
                from core import hitl_reject_delivery as delivery
                for statement, args in (
                    (delivery._CLAIM_SQL, ("TEN-CI",)),
                    (delivery._LEASE_SQL, ("svc-CI", "token-CI", "EVT-CI")),
                    (delivery._ACK_SQL, ("TEN-CI", "EVT-CI")),
                    (delivery._DELIVER_SQL, ("EVT-CI", "svc-CI", "token-CI")),
                ):
                    with self.subTest(stage="reject_delivery_sql_plan"):
                        self.assertTrue(conn.execute("EXPLAIN " + statement, args).fetchall())
                conn.execute(
                    "insert into aiops.tenant_resource_ownership "
                    "(resource_kind,resource_id,tenant_id,source_event_id,"
                    "verified,observed_at,known_at) "
                    "values ('glpi_entity','CI-ENTITY','TEN-CI','SRC-CI',true,now(),now())")
                with self.assertRaises(psycopg.Error):
                    conn.execute(
                        "update aiops.tenant_resource_ownership "
                        "set tenant_id='TEN-FOREIGN' where resource_id='CI-ENTITY'")
                conn.rollback()
        finally:
            if created:
                with psycopg.connect(raw_url, autocommit=True) as admin:
                    admin.execute(psql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                        psql.Identifier(database_name)))


# Existing architect-owned Quality command discovers this imported Core-only PG16
# suite without modifying the shared workflow. The class is disposable-only.
from test_core_hitl_reject_pg16_populated import CoreRejectPopulatedPG16
from test_core_actor_nonce_pg16 import ActorLedgerStaticTests, ActorLedgerPopulatedPG16
from test_core_actor_pg16_archive_restore import CoreActorArchiveRestorePG16

if __name__ == "__main__":
    unittest.main()
