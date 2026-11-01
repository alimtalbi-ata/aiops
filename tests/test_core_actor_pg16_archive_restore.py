"""Disposable PostgreSQL 16 archive/restore rehearsal for Core actor audit.

Never targets a non-loopback database. Never drops 013 audit tables in a
populated source. Restoring to a NEW disposable database is not an in-place
production downgrade. This test is imported by the existing installed gate.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from urllib.parse import unquote, urlsplit, urlunsplit

MIG = Path(__file__).resolve().parent.parent / "db" / "migrations"
ORDER = ("001_schema.sql", "004_operational_model.sql",
         "009_ai_decision_ledger.sql", "010_evidence_identity.sql",
         "011_hitl_decision_outbox.sql", "012_itsm_xref_read.sql",
         "013_actor_delegation_replay_ledger.sql")


def _hash(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


@unittest.skipUnless(os.environ.get("AIOPS_XREF_CI_DISPOSABLE") == "1"
                     and os.environ.get("GITHUB_ACTIONS") == "true",
                     "requires disposable GitHub Actions PostgreSQL 16")
class CoreActorArchiveRestorePG16(unittest.TestCase):
    def test_full_pg_dump_restore_populated_009_to_013_audit_preserved(self):
        import psycopg
        from psycopg import sql

        p = urlsplit(os.environ["DATABASE_URL"])
        if (p.scheme not in ("postgres", "postgresql")
                or p.hostname != "127.0.0.1" or p.port != 5432
                or p.path != "/aiops" or p.username != "aiops"
                or p.query or p.fragment):
            raise RuntimeError("Refusing non-disposable PostgreSQL target")
        # Hosted runners may have PG18 clients against a PG16 disposable
        # server. Decode the custom archive through pg_restore, remove only
        # PG18's unsupported transaction_timeout SET, and execute with psql
        # ON_ERROR_STOP. Never suppress any other SQL error.
        dump, restore, psql = (shutil.which(name)
                               for name in ("pg_dump", "pg_restore", "psql"))
        if not all((dump, restore, psql)):
            self.fail("pg_dump, pg_restore and psql clients are required")
        env = dict(os.environ)
        env["PGPASSWORD"] = unquote(p.password or "")
        env["PGCONNECT_TIMEOUT"] = "5"
        # Names are exclusive to this gate. CREATE fails closed if preexisting.
        source = "aiops_actor_archive_ci"
        target = "aiops_actor_restore_ci"
        created = []
        def dburl(name):
            return urlunsplit((p.scheme, p.netloc, "/" + name, "", ""))
        try:
            with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as admin:
                version = int(admin.execute("show server_version_num").fetchone()[0])
                self.assertTrue(160000 <= version < 170000)
                for name in (source, target):
                    admin.execute(sql.SQL("create database {}").format(sql.Identifier(name)))
                    created.append(name)
            with psycopg.connect(dburl(source)) as conn:
                for name in ORDER:
                    conn.execute((MIG / name).read_text(encoding="utf-8"))
                # Populated source: immutable owner and 013 nonce/revocation rows.
                conn.execute(
                    "insert into aiops.tenant_resource_ownership "
                    "(resource_kind,resource_id,tenant_id,source_event_id,"
                    "verified,observed_at,known_at) "
                    "values ('glpi_entity','GLPI-A:7','TEN-A','SRC-ARCHIVE',"
                    "true,now(),now())")
                consumed = conn.execute(
                    "select aiops.actor_delegation_consume(%s,%s,%s,%s,%s,%s,"
                    "clock_timestamp() + interval '120 seconds')",
                    ("TEN-A", "https://issuer.example.invalid", _hash("subject"),
                     _hash("archive-jti"), _hash("archive-nonce"),
                     _hash("TEN-A|RUN-A|INC-A|123|7|run:read"))).fetchone()[0]
                self.assertTrue(consumed)
                self.assertTrue(conn.execute(
                    "select aiops.actor_delegation_revoke(%s,%s,%s)",
                    ("https://issuer.example.invalid", _hash("revoked-jti"),
                     "REV-ARCHIVE")).fetchone()[0])
            tables = ("tenant_resource_ownership",
                      "actor_delegation_nonce_ledger",
                      "actor_delegation_revocations")
            def snapshot(url):
                with psycopg.connect(url) as conn:
                    return {
                        table: conn.execute(
                            "select * from aiops." + table +
                            " order by 1, 2").fetchall()
                        for table in tables
                    }
            before = snapshot(dburl(source))
            self.assertEqual([len(before[t]) for t in tables], [1, 1, 1])
            with tempfile.TemporaryDirectory(prefix="aiops-actor-archive-") as tmp:
                archive = str(Path(tmp) / "core-audit.pgcustom")
                common = ["--host=127.0.0.1", "--port=5432",
                          "--username=aiops", "--no-owner", "--no-acl"]
                subprocess.run([dump, *common, "--format=custom",
                                "--file=" + archive, source],
                               env=env, check=True, timeout=60,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                self.assertGreater(Path(archive).stat().st_size, 1000)
                sqlfile = Path(tmp) / "restore.sql"
                subprocess.run(
                    [restore, "--no-owner", "--no-acl",
                     "--file=" + str(sqlfile), archive],
                    env=env, check=True, timeout=90,
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                script = sqlfile.read_text(encoding="utf-8")
                incompatible = "SET transaction_timeout = 0;\n"
                self.assertLessEqual(script.count(incompatible), 1)
                # PostgreSQL 16 does not support the PG18-only SET; no data,
                # DDL or immutable ledger statement is changed.
                script = script.replace(incompatible, "")
                sqlfile.write_text(script, encoding="utf-8")
                restored = subprocess.run(
                    [psql, "--host=127.0.0.1", "--port=5432",
                     "--username=aiops", "--set=ON_ERROR_STOP=1",
                     "--dbname=" + target, "--file=" + str(sqlfile)],
                    env=env, check=False, timeout=90,
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                self.assertEqual(
                    restored.returncode, 0,
                    "Disposable pg_restore SQL replay failed: " +
                    restored.stderr.decode("utf-8", errors="replace")[-1800:])
            self.assertEqual(snapshot(dburl(target)), before)
            with psycopg.connect(dburl(target)) as conn:
                # An archive restore must retain the negative replay fence.
                self.assertFalse(conn.execute(
                    "select aiops.actor_delegation_consume(%s,%s,%s,%s,%s,%s,"
                    "clock_timestamp() + interval '120 seconds')",
                    ("TEN-A", "https://issuer.example.invalid", _hash("subject"),
                     _hash("archive-jti"), _hash("archive-nonce"),
                     _hash("TEN-A|RUN-A|INC-A|123|7|run:read"))).fetchone()[0])
                self.assertFalse(conn.execute(
                    "select aiops.actor_delegation_consume(%s,%s,%s,%s,%s,%s,"
                    "clock_timestamp() + interval '120 seconds')",
                    ("TEN-A", "https://issuer.example.invalid", _hash("subject"),
                     _hash("revoked-jti"), _hash("new-nonce"),
                     _hash("TEN-A|RUN-A|INC-A|123|7|run:read"))).fetchone()[0])
                # Reapply 009-013 on populated restore, without losing rows.
                for name in ORDER[2:]:
                    conn.execute((MIG / name).read_text(encoding="utf-8"))
            self.assertEqual(snapshot(dburl(target)), before)
            # Code-only rollback rehearsal: source audit stays untouched;
            # no DROP TABLE/SCHEMA and no deletion of immutable 013 rows.
            self.assertEqual(snapshot(dburl(source)), before)
        finally:
            with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as admin:
                for name in reversed(created):
                    admin.execute(sql.SQL("drop database {} with (force)").format(
                        sql.Identifier(name)))


if __name__ == "__main__":
    unittest.main()
