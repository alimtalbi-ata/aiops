"""Real disposable PG16 actor JTI/nonce/revocation fence, after installed 009-012.

Never targets production or a non-loopback PostgreSQL instance. No GLPI I/O.
"""
import concurrent.futures
import hashlib
import os
from pathlib import Path
import unittest
from urllib.parse import urlsplit, urlunsplit

MIG = Path(__file__).resolve().parent.parent / "db" / "migrations"
ORDER = ("001_schema.sql", "004_operational_model.sql",
         "009_ai_decision_ledger.sql", "010_evidence_identity.sql",
         "011_hitl_decision_outbox.sql", "012_itsm_xref_read.sql",
         "013_actor_delegation_replay_ledger.sql")


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class ActorLedgerStaticTests(unittest.TestCase):
    def test_013_follows_installed_012_and_is_append_only(self):
        body = (MIG / ORDER[-1]).read_text(encoding="utf-8").lower()
        for required in ("actor_delegation_nonce_ledger", "actor_delegation_revocations",
                         "actor_delegation_consume", "actor_delegation_revoke",
                         "pg_advisory_xact_lock", "on conflict do nothing",
                         "trg_actor_nonce_immutable", "trg_actor_revocation_immutable",
                         "clock_timestamp()"):
            with self.subTest(required=required):
                self.assertIn(required, body)
        self.assertEqual([s[:3] for s in ORDER[-5:]],
                         ["009", "010", "011", "012", "013"])


@unittest.skipUnless(os.environ.get("AIOPS_XREF_CI_DISPOSABLE") == "1"
                     and os.environ.get("GITHUB_ACTIONS") == "true",
                     "requires GitHub Actions disposable loopback PostgreSQL 16")
class ActorLedgerPopulatedPG16(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        from psycopg import sql
        cls.psycopg = psycopg
        cls.sql = sql
        raw = os.environ["DATABASE_URL"]
        p = urlsplit(raw)
        if (p.scheme not in ("postgres", "postgresql")
                or p.hostname != "127.0.0.1" or p.port != 5432
                or p.path != "/aiops" or p.username != "aiops"
                or p.query or p.fragment):
            raise RuntimeError("Refusing non-disposable PostgreSQL target")
        cls.admin_url = raw
        cls.database_name = "aiops_actor_nonce_ci"
        cls.url = urlunsplit((p.scheme, p.netloc, "/" + cls.database_name, "", ""))
        cls.created = False
        with psycopg.connect(raw, autocommit=True) as conn:
            v = int(conn.execute("show server_version_num").fetchone()[0])
            if not 160000 <= v < 170000:
                raise RuntimeError("PostgreSQL 16 only")
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(cls.database_name)))
            cls.created = True
        try:
            with psycopg.connect(cls.url) as conn:
                for name in ORDER:
                    conn.execute((MIG / name).read_text(encoding="utf-8"))
                # Real installed upgrade, then repeat 013 without data loss.
                conn.execute((MIG / ORDER[-1]).read_text(encoding="utf-8"))
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "created", False):
            with cls.psycopg.connect(cls.admin_url, autocommit=True) as conn:
                conn.execute(cls.sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                    cls.sql.Identifier(cls.database_name)))

    def consume(self, conn, jti, nonce, tenant="TEN-A", expiry="120 seconds"):
        return conn.execute(
            "select aiops.actor_delegation_consume(%s,%s,%s,%s,%s,%s,"
            "clock_timestamp() + (%s)::interval)",
            (tenant, "https://issuer.example.invalid", sha("subject-A"), sha(jti),
             sha(nonce), sha("TEN-A|RUN-A|INC-A|123|7|run:read"), expiry)).fetchone()[0]

    def revoke(self, conn, jti):
        return conn.execute("select aiops.actor_delegation_revoke(%s,%s,%s)",
                            ("https://issuer.example.invalid", sha(jti), "REV-001")).fetchone()[0]

    def test_populated_replay_nonce_collision_revocation_and_expiry(self):
        with self.psycopg.connect(self.url) as conn:
            before = conn.execute("select count(*) from aiops.actor_delegation_nonce_ledger").fetchone()[0]
            self.assertTrue(self.consume(conn, "jti-A", "nonce-A"))
            self.assertFalse(self.consume(conn, "jti-A", "nonce-A"))
            self.assertFalse(self.consume(conn, "jti-B", "nonce-A"))
            self.assertFalse(self.consume(conn, "jti-A", "nonce-B", tenant="TEN-B"))
            self.assertFalse(self.consume(conn, "jti-expired", "nonce-expired", expiry="-1 second"))
            self.assertTrue(self.revoke(conn, "jti-revoked-before"))
            self.assertFalse(self.consume(conn, "jti-revoked-before", "nonce-revoked"))
            self.assertTrue(self.consume(conn, "jti-revoked-after", "nonce-later"))
            self.assertTrue(self.revoke(conn, "jti-revoked-after"))
            self.assertFalse(self.consume(conn, "jti-revoked-after", "nonce-later2"))
            self.assertFalse(self.revoke(conn, "jti-revoked-after"))
            self.assertEqual(conn.execute(
                "select count(*) from aiops.actor_delegation_nonce_ledger").fetchone()[0], before + 2)
            self.assertEqual(conn.execute(
                "select count(*) from aiops.actor_delegation_revocations").fetchone()[0], 2)

    def test_concurrent_single_winner_and_populated_transaction_rollback(self):
        def compete(_):
            with self.psycopg.connect(self.url) as conn:
                return self.consume(conn, "jti-race", "nonce-race")
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(compete, range(2)))
        self.assertEqual(sorted(results), [False, True])
        with self.psycopg.connect(self.url) as conn:
            before = conn.execute(
                "select count(*) from aiops.actor_delegation_nonce_ledger").fetchone()[0]
            # Reapply installed 013 with rows already present.
            conn.execute((MIG / ORDER[-1]).read_text(encoding="utf-8"))
            self.assertEqual(conn.execute(
                "select count(*) from aiops.actor_delegation_nonce_ledger").fetchone()[0], before)
            # A transactional schema rollback restores *populated* tables.
            conn.execute("drop table aiops.actor_delegation_nonce_ledger cascade")
            self.assertIsNone(conn.execute(
                "select to_regclass('aiops.actor_delegation_nonce_ledger')").fetchone()[0])
            conn.rollback()
        with self.psycopg.connect(self.url) as conn:
            self.assertEqual(conn.execute(
                "select count(*) from aiops.actor_delegation_nonce_ledger").fetchone()[0], before)
            with self.assertRaises(self.psycopg.Error):
                conn.execute("delete from aiops.actor_delegation_nonce_ledger")
            conn.rollback()
            # Ensure a row exists: PostgreSQL does not fire row triggers on an
            # UPDATE matching zero rows. Roll this synthetic revocation back.
            conn.execute("select aiops.actor_delegation_revoke(%s,%s,%s)",
                         ("https://issuer.example.invalid", sha("jti-trigger"), "REV-TRIGGER"))
            with self.assertRaises(self.psycopg.Error):
                conn.execute("update aiops.actor_delegation_revocations set source_event_id='EVIL'")
            conn.rollback()


if __name__ == "__main__":
    unittest.main()
