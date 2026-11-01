"""Core /events + /command writer on installed disposable PG16 001/004/009-015.

Tests the real canonical ASGI app, not a fake router. Source observations and
actor IDs are synthetic; legacy internal bearer is NOT human IdP/GLPI ACL.
No Debian DB, GLPI writes, LIVE, or immutable 013/014 audit mutation.
"""
import hashlib
import json
import os
import secrets
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit, urlunsplit

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "db/migrations"
CHAIN = ("001_schema.sql", "004_operational_model.sql",
         "009_ai_decision_ledger.sql", "010_evidence_identity.sql",
         "011_hitl_decision_outbox.sql", "012_itsm_xref_read.sql",
         "013_actor_delegation_replay_ledger.sql",
         "014_hitl_reject_terminal_receipts.sql")
LATEST = "015_core_run_event_idempotency.sql"


@unittest.skipUnless(os.getenv("AIOPS_XREF_CI_DISPOSABLE") == "1"
                     and os.getenv("GITHUB_ACTIONS") == "true",
                     "disposable PostgreSQL 16 CI only")
class CoreRunEventKey015PG16(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        from psycopg import sql
        cls.psycopg, cls.sql = psycopg, sql
        raw = os.environ["DATABASE_URL"]
        parsed = urlsplit(raw)
        if (parsed.scheme not in ("postgres", "postgresql")
                or parsed.hostname != "127.0.0.1" or parsed.port != 5432
                or parsed.username != "aiops" or parsed.path != "/aiops"
                or parsed.query or parsed.fragment):
            raise RuntimeError("refuse non-disposable PostgreSQL")
        cls.admin = raw
        cls.name = "aiops_core_writer_015_ci"
        cls.url = urlunsplit((parsed.scheme, parsed.netloc,
                              "/" + cls.name, "", ""))
        cls.created = False
        with psycopg.connect(raw, autocommit=True) as conn:
            version = int(conn.execute("show server_version_num").fetchone()[0])
            if not 160000 <= version < 170000:
                raise RuntimeError("requires PG16")
            conn.execute(sql.SQL("create database {}").format(sql.Identifier(cls.name)))
            cls.created = True
        try:
            with psycopg.connect(cls.url) as conn:
                for file in CHAIN:
                    conn.execute((MIG / file).read_text())
            cls.token = secrets.token_urlsafe(40)
            cls.env = patch.dict(os.environ, {
                "AIOPS_INTERNAL_TOKEN": cls.token, "DATABASE_URL": cls.url,
            })
            cls.env.start()
            from core import main
            cls.core = main
            cls.admin_patch = patch.object(main, "ADMIN", cls.token)
            cls.db_patch = patch.object(main, "db",
                                        side_effect=lambda: psycopg.connect(cls.url))
            cls.admin_patch.start()
            cls.db_patch.start()
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        for key in ("db_patch", "admin_patch", "env"):
            if hasattr(cls, key):
                getattr(cls, key).stop()
        if getattr(cls, "created", False):
            with cls.psycopg.connect(cls.admin, autocommit=True) as conn:
                conn.execute(cls.sql.SQL("drop database {} with (force)").format(
                    cls.sql.Identifier(cls.name)))

    def test_01_forward_migration_transactional_rollback_and_idempotence(self):
        script = (MIG / LATEST).read_text()
        self.assertFalse(any(s in script.lower() for s in (
            "drop table", "drop column", "truncate", "delete from")))
        self.assertEqual(len(list(MIG.glob("015_*.sql"))), 1)
        with self.psycopg.connect(self.url) as conn:
            self.assertIsNone(conn.execute(
                "select 1 from information_schema.columns where "
                "table_schema='aiops' and table_name='run_events' "
                "and column_name='event_key'").fetchone())
            conn.execute(script)
            self.assertIsNotNone(conn.execute(
                "select 1 from information_schema.columns where "
                "table_schema='aiops' and table_name='run_events' "
                "and column_name='event_key'").fetchone())
            conn.rollback()
        with self.psycopg.connect(self.url) as conn:
            self.assertIsNone(conn.execute(
                "select 1 from information_schema.columns where "
                "table_schema='aiops' and table_name='run_events' "
                "and column_name='event_key'").fetchone())
        for _ in range(2):
            with self.psycopg.connect(self.url) as conn:
                conn.execute(script)
        with self.psycopg.connect(self.url) as conn:
            self.assertIsNotNone(conn.execute(
                "select indexdef from pg_indexes where schemaname='aiops' "
                "and tablename='run_events' and indexname='ux_run_events_event_key'"
            ).fetchone())
            self.assertEqual(conn.execute(
                "select count(*) from pg_trigger where tgname in "
                "('trg_actor_nonce_immutable','trg_actor_revocation_immutable',"
                "'trg_hitl_reject_terminal_immutable') and not tgisinternal"
            ).fetchone()[0], 3)

    def test_02_real_asgi_seven_events_command_negatives_and_native_restore(self):
        incident, rid = "INC-SYN-EVT-CI", "RUN-SYN-EVT-CI"
        with self.psycopg.connect(self.url) as conn:
            conn.execute(
                "insert into aiops.incidents(incident_id,title,severity,state,"
                "opened_at,source,synthetic,payload) "
                "values(%s,'synthetic SAN','P4','OPEN',now(),'ci',true,%s)",
                (incident, json.dumps({"tenant_id":"TEN-CI","synthetic":True})))
            conn.execute(
                "insert into aiops.runs(run_id,incident_id,mode,scenario_id,"
                "status,idempotency_key) values(%s,%s,'DEMO','ACME-CI',"
                "'CREATED','ci-run-015')", (rid, incident))
            for i in range(1, 8):
                payload = {"tenant_id":"TEN-CI","incident_id":incident,
                           "run_id":rid,"source_event_id":f"SYN-EVT-{i:02d}",
                           "sequence":i,"synthetic":True,
                           "actor_id":"svc-ci","metric":f"synthetic-{i}"}
                conn.execute(
                    "insert into aiops.evidence(evidence_id,source,external_id,"
                    "observed_at,claim,confidence,provenance,payload_hash,payload)"
                    " values(%s,'CORE_CI_SYNTHETIC',%s,now(),'synthetic',0.5,"
                    "%s,%s,%s)",
                    (f"EVI-SYN-{i}",f"SYN-EVT-{i:02d}",
                     json.dumps({"tenant_id":"TEN-CI","incident_id":incident,
                                 "run_id":rid,"actor_id":"svc-ci"}),
                     hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest(),
                     json.dumps(payload)))
        route = f"/api/runs/{rid}"
        headers = {"Authorization":"Bearer "+self.token}
        negatives = {}
        with TestClient(self.core.app, raise_server_exceptions=False) as client:
            before = client.get(route).json()
            self.assertEqual((before["run"]["version"],len(before["events"])),(1,0))
            def body(i, version):
                return {"expected_version":version,"stage":"INGEST",
                        "event_type":"SYNTHETIC_SOURCE_EVENT","status":"PASS",
                        "event_key":f"SYN-EVT-{i:02d}",
                        "evidence_ids":[f"EVI-SYN-{i}"],
                        "payload":{"tenant_id":"TEN-CI","incident_id":incident,
                                   "run_id":rid,"source_event_id":f"SYN-EVT-{i:02d}",
                                   "sequence":i,"synthetic":True,
                                   "actor_id":"svc-ci","metric":f"synthetic-{i}"}}
            negatives["bad_token"] = client.post(route+"/events",
                json=body(1,1),headers={"Authorization":"Bearer bad"}).status_code
            negatives["foreign_run"] = client.post(
                "/api/runs/RUN-FOREIGN/events",json=body(1,1),headers=headers).status_code
            negatives["invalid_stage"] = client.post(route+"/events",
                json={**body(1,1),"stage":"INVALID"},headers=headers).status_code
            negatives["unknown_evidence"] = client.post(route+"/events",
                json={**body(1,1),"evidence_ids":["EVI-NOT-FOUND"]},
                headers=headers).status_code
            negatives["stale_version"] = client.post(route+"/events",
                json=body(1,99),headers=headers).status_code
            self.assertEqual(negatives, {
                "bad_token":401,"foreign_run":404,"invalid_stage":422,
                "unknown_evidence":422,"stale_version":409})
            version=1
            for i in range(1,8):
                response=client.post(route+"/events",json=body(i,version),
                                     headers=headers)
                self.assertEqual(response.status_code,200,response.text)
                self.assertEqual(response.json()["sequence"],i)
                self.assertIs(response.json()["idempotent"],False)
                version=response.json()["version"]
            self.assertEqual(version,8)
            replay=client.post(route+"/events",json=body(1,1),headers=headers)
            self.assertEqual((replay.status_code,replay.json()["idempotent"]),(200,True))
            negatives["conflicting_event_key"]=client.post(
                route+"/events",
                json={**body(1,version),"payload":{"synthetic":False}},
                headers=headers).status_code
            self.assertEqual(negatives["conflicting_event_key"],409)
            cmd={"expected_version":version,"idempotency_key":"ci-start-015",
                 "command":"START"}
            response=client.post(route+"/command",json=cmd,headers=headers)
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()["status"],"RUNNING")
            replay=client.post(route+"/command",json=cmd,headers=headers)
            self.assertEqual((replay.status_code,replay.json()),
                             (200,response.json()))
            negatives["conflicting_command_key"]=client.post(
                route+"/command",json={**cmd,"command":"WAIT"},headers=headers
            ).status_code
            self.assertEqual(negatives["conflicting_command_key"],409)
            # Force an exception AFTER SQL INSERT, proving transaction rollback.
            original=self.core.append_event
            def fail_after_insert(*args,**kwargs):
                original(*args,**kwargs)
                raise RuntimeError("synthetic SQL failure after insert")
            with patch.object(self.core,"append_event",side_effect=fail_after_insert):
                failed=client.post(route+"/events",json=body(7,9)|{
                    "event_key":"SYN-EVT-ROLLBACK"},headers=headers)
            self.assertEqual(failed.status_code,500)
            after=client.get(route).json()
            self.assertEqual((after["run"]["status"],after["run"]["version"],
                              len(after["events"])),("RUNNING",9,8))
        with self.psycopg.connect(self.url) as conn:
            self.assertEqual(conn.execute(
                "select count(*) from aiops.run_events where run_id=%s "
                "and event_key='SYN-EVT-ROLLBACK'",(rid,)).fetchone()[0],0)
            self.assertEqual(conn.execute(
                "select count(*) from aiops.command_receipts where run_id=%s",
                (rid,)).fetchone()[0],1)
            audit={k:conn.execute("select count(*) from aiops."+table).fetchone()[0]
                   for k,table in (
                       ("nonce_013","actor_delegation_nonce_ledger"),
                       ("revocation_013","actor_delegation_revocations"),
                       ("terminal_014","hitl_reject_terminal_receipts"))}
            self.assertEqual(audit,{"nonce_013":0,"revocation_013":0,
                                    "terminal_014":0})
        with tempfile.TemporaryDirectory(prefix="core-015-pg16-") as tmp:
            dump=Path(tmp)/"backup.dump"
            restored="aiops_core_writer_015_restore_ci"
            restore_url=self.url.replace("/"+self.name,"/"+restored)
            with self.psycopg.connect(self.admin,autocommit=True) as conn:
                conn.execute(self.sql.SQL("create database {}").format(
                    self.sql.Identifier(restored)))
            try:
                subprocess.run(["pg_dump","--format=custom","--file",str(dump),
                                "--dbname",self.url],check=True,
                               stdout=subprocess.DEVNULL)
                subprocess.run(["pg_restore","--single-transaction",
                                "--no-owner","--no-acl","--dbname",restore_url,
                                str(dump)],check=True,stdout=subprocess.DEVNULL)
                with self.psycopg.connect(restore_url) as conn:
                    self.assertEqual(conn.execute(
                        "select count(*) from aiops.run_events where run_id=%s",
                        (rid,)).fetchone()[0],8)
                    self.assertEqual(conn.execute(
                        "select count(*) from aiops.command_receipts where run_id=%s",
                        (rid,)).fetchone()[0],1)
                    self.assertEqual(conn.execute(
                        "select count(*) from pg_trigger where tgname in "
                        "('trg_actor_nonce_immutable','trg_actor_revocation_immutable',"
                        "'trg_hitl_reject_terminal_immutable') and not tgisinternal"
                    ).fetchone()[0],3)
                archive_sha=hashlib.sha256(dump.read_bytes()).hexdigest()
            finally:
                with self.psycopg.connect(self.admin,autocommit=True) as conn:
                    conn.execute(self.sql.SQL("drop database {} with (force)").format(
                        self.sql.Identifier(restored)))
        receipt={
            "schema":"aiops.core-run-event-key-015-ci.v1",
            "source_head":os.environ["AIOPS_EXPECTED_HEAD_SHA"],
            "installed":[x[:3] for x in CHAIN]+["015"],
            "run_events":8,"source_events":7,"command_receipts":1,
            "negative_http":negatives,"injected_sql_rollback":True,
            "native_pg16_restore":True,"archive_sha256":archive_sha,
            "archive_retained":False,"audit_rows":audit,
            "human_glpi_allow":False,"actor_tenant_attested":False,
            "source_authority":"SYNTHETIC_FIXTURE_ONLY",
            "release_stable":"NO_GO",
            "rollback":"CODE_ONLY_KEEP_013_014_AUDIT",
        }
        receipt["payload_sha256"]=hashlib.sha256(json.dumps(
            receipt,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        target=Path(os.environ["AIOPS_CORE_WRITER_RECEIPT_DIR"])
        self.assertTrue(str(target).startswith("/tmp/core-015-"))
        target.mkdir(parents=True,exist_ok=True)
        (target/"core-writer-015.json").write_text(
            json.dumps(receipt,sort_keys=True,indent=2)+"\n")
