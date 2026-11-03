"""Native same-major PostgreSQL 16 archive/restore and SHA256 audit rehearsal.

Never targets a non-loopback database. Never drops 013 audit tables in a
populated source. Restoring to a NEW disposable database is not an in-place
production downgrade. Uses native PG16 clients, never PG18 SQL rewrites.
"""
from __future__ import annotations

import hashlib
import json
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
class CoreActorNativeArchiveRestorePG16(unittest.TestCase):
    def test_native_pg16_sha256_archive_restore_populated_009_to_013(self):
        import psycopg
        from psycopg import sql

        p = urlsplit(os.environ["DATABASE_URL"])
        if (p.scheme not in ("postgres", "postgresql")
                or p.hostname != "127.0.0.1" or p.port != 5432
                or p.path != "/aiops" or p.username != "aiops"
                or p.query or p.fragment):
            raise RuntimeError("Refusing non-disposable PostgreSQL target")
        # Same-major clients only. A PG18 pg_restore SQL conversion is NOT
        # accepted as native PG16 disaster recovery evidence.
        client_dir = Path("/usr/lib/postgresql/16/bin")
        dump, restore = (str(client_dir / name)
                         for name in ("pg_dump", "pg_restore"))
        for binary in (dump, restore):
            self.assertTrue(Path(binary).is_file(),
                            "NOT_QUALIFIED: required native PG16 client missing: " + binary)
            version = subprocess.run(
                [binary, "--version"], capture_output=True, text=True,
                check=True, timeout=10).stdout
            self.assertIn("(PostgreSQL) 16.", version)
        artifact_dir = os.environ.get("AIOPS_PG16_RECOVERY_ARTIFACT_DIR")
        self.assertTrue(artifact_dir, "Dedicated CI must retain SHA256 recovery evidence")
        env = dict(os.environ)
        env["PGPASSWORD"] = unquote(p.password or "")
        env["PGCONNECT_TIMEOUT"] = "5"
        # Names are exclusive to this gate. CREATE fails closed if preexisting.
        source = "aiops_actor_native_archive_ci"
        target = "aiops_actor_native_restore_ci"
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
            with tempfile.TemporaryDirectory(prefix="aiops-pg16-native-archive-") as tmp:
                archive = Path(tmp) / "core-audit.pgcustom"
                common = ["--host=127.0.0.1", "--port=5432",
                          "--username=aiops", "--no-owner", "--no-acl"]
                subprocess.run(
                    [dump, *common, "--format=custom",
                     "--file=" + str(archive), source],
                    env=env, check=True, timeout=60,
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                self.assertGreater(archive.stat().st_size, 1000)
                expected_sha256 = hashlib.sha256(archive.read_bytes()).hexdigest()
                self.assertEqual(len(expected_sha256), 64)
                # Simulate archive transfer to a second restore location.
                restored_input = Path(tmp) / "verified-restore-input.pgcustom"
                shutil.copyfile(archive, restored_input)
                def verify_archive(path):
                    actual = hashlib.sha256(path.read_bytes()).hexdigest()
                    if actual != expected_sha256:
                        raise ValueError("SHA256 mismatch: refuse recovery")
                    return actual
                self.assertEqual(verify_archive(restored_input), expected_sha256)
                # A deliberately corrupted copy MUST fail the checksum gate
                # before any pg_restore invocation.
                tampered = Path(tmp) / "tampered.pgcustom"
                shutil.copyfile(archive, tampered)
                with tampered.open("ab") as stream:
                    stream.write(b"tampered")
                with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                    verify_archive(tampered)
                # Native PG16 pg_restore direct to a NEW empty disposable DB,
                # with atomic restore and strict exit-on-error. No SQL rewrite.
                result = subprocess.run(
                    [restore, *common, "--single-transaction",
                     "--exit-on-error", "--dbname=" + target,
                     str(restored_input)],
                    env=env, check=False, timeout=90,
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                self.assertEqual(
                    result.returncode, 0,
                    "Native PostgreSQL 16 restore failed: " +
                    result.stderr.decode("utf-8", errors="replace")[-1800:])
                self.assertEqual(verify_archive(restored_input), expected_sha256)
                # Publish only synthetic CI data; never publish DB credentials.
                out = Path(artifact_dir)
                out.mkdir(parents=True, exist_ok=True)
                retained = out / "core-audit.pgcustom"
                shutil.copyfile(restored_input, retained)
                self.assertEqual(verify_archive(retained), expected_sha256)
                (out / "core-audit.pgcustom.sha256").write_text(
                    expected_sha256 + "  core-audit.pgcustom\n", encoding="ascii")
                (out / "recovery-manifest.json").write_text(
                    json.dumps({
                        "mode": "DISPOSABLE_SYNTHETIC_ONLY",
                        "server_major": 16, "client_major": 16,
                        "migrations": list(ORDER),
                        "archive_sha256": expected_sha256,
                        "source_rows": {"tenant_resource_ownership": 1,
                                        "actor_delegation_nonce_ledger": 1,
                                        "actor_delegation_revocations": 1},
                        "recovery": "PG16_NATIVE_SINGLE_TRANSACTION",
                        "rollback": "CODE_ONLY_AUDIT_013_PRESERVED",
                        "authorization": "UNKNOWN"
                    }, sort_keys=True, indent=2) + "\n", encoding="utf-8")
                print("DISPOSABLE_PG16_ARCHIVE_SHA256=" + expected_sha256)
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
