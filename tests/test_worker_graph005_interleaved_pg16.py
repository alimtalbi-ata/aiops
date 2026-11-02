"""Worker-owned disposable graph005 same-Run / two-OS-PID negative regression.

Actual Core HTTP ASGI writer and PG16 are exercised by two independent
Temporal test Worker OS processes. The event appender is a CI harness, NOT
the production Worker execution path or a human GLPI/IdP authorization.
No APPROVE, signal, executor, LIVE, or GLPI write is possible here.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from temporalio.testing import WorkflowEnvironment

import test_core_actor_canonical_seven_pg16 as fixture
from core import actor_canonical_seven_source as binding
from core import canonical_seven_pg_source as source

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "ci-graph005-worker-writer-only"

# A real, separate OS process runs a disposable Temporal Worker and writes its
# stage through Core's HTTP API, never by direct SQL or an invented receipt.
WORKER_CODE = """
import asyncio, os, sys
from pathlib import Path
from unittest.mock import patch
import psycopg
from fastapi.testclient import TestClient
from temporalio.client import Client
from temporalio.worker import Worker
from test_worker_hitl_reject_notification import SyntheticRejectSink
from core import main

db_url, run, target, queue, ready, stage, version, command, done = sys.argv[1:]
def append(stage, version, key, status, decision, payload):
    with patch.object(main, "db", side_effect=lambda: psycopg.connect(db_url)):
        with TestClient(main.app) as api:
            response = api.post(f"/api/runs/{run}/events",
                json={"expected_version": int(version), "stage": stage,
                      "event_type": "WORKFLOW_OBSERVATION", "status": status,
                      "event_key": key, "evidence_ids": [],
                      "decision": decision, "payload": payload},
                headers={"Authorization": "Bearer " + os.environ["AIOPS_INTERNAL_TOKEN"]})
            if response.status_code != 200 or response.json().get("idempotent"):
                raise RuntimeError("worker_core_append_failed:" + str(response.status_code))
async def main_loop():
    global command
    if stage == "DGX_ANALYST":
        append(stage, version, "worker-graph005-analyst", "PASS", None,
               {"synthetic": True, "analysis": "UNVERIFIED"})
    else:
        append(stage, version, "worker-graph005-verify", "BLOCKED", "UNVERIFIED",
               {"synthetic": True, "verification": "UNVERIFIED"})
    client = await Client.connect(target)
    async with Worker(client, task_queue=queue, workflows=[SyntheticRejectSink]):
        Path(ready).write_text("ready")
        while True:
            if command != "-" and Path(command).is_file():
                append("HITL", 10, "worker-graph005-reject", "BLOCKED", "REJECT",
                       {"synthetic": True, "reopen": "RECOMMENDED_NOT_EXECUTED",
                        "execution_allowed": False, "effect_allowed": False})
                Path(done).write_text("done")
                command = "-"
            await asyncio.sleep(0.05)
asyncio.run(main_loop())
"""


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@unittest.skipUnless(
    os.environ.get("GITHUB_ACTIONS") == "true"
    and os.environ.get("AIOPS_XREF_CI_DISPOSABLE") == "1"
    and os.environ.get("AIOPS_CI_GRAPH005_WORKER") == "YES",
    "requires explicitly disposable GitHub PG16 and Temporal services",
)
class Graph005TwoOSWorker(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        # Reuse Core's already-qualified PG16 disposable schema fixture, not
        # Core test methods or their synthetic Worker-shaped event fixtures.
        fixture.CanonicalSevenSourcePG16.setUpClass()
        cls.pg = fixture.CanonicalSevenSourcePG16

    @classmethod
    def tearDownClass(cls):
        fixture.CanonicalSevenSourcePG16.tearDownClass()

    async def test_same_run_interleaved_worker_pids_revoke_replay_no_effect(self):
        with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": TOKEN}):
            from core import main
        from tools import generate_acme_incidents as gen

        pg = self.pg
        pinned = json.loads((ROOT / "docs/customer-story/"
            "ACME-CORE015-V3-CANONICAL-NEGATIVE-2026-11-02.json").read_text())
        replay = gen.replay(seed=20261018)
        self.assertEqual(pinned["graph_version"], replay["graph_version"])
        expected = tuple((e["source_event_id"], e["acme_full_event_sha256"],
                          e["acme_local_payload_sha256"]) for e in pinned["events"])
        self.assertEqual(len(expected), 7)
        tenant, incident, run = "TEN-GRAPH005-WORKER", "INC-GRAPH005-WORKER", "RUN-GRAPH005-WORKER"
        actor, issuer, source_issuer = "idp|worker-ci", fixture.ISSUER, "core-graph005-disposable-source"
        scope = dict(tenant_id=tenant, incident_id=incident, run_id=run,
                     glpi_instance_id="GLPI-W", ticket_id="777", glpi_entity_id="33",
                     permission="run:read", actor_subject=actor, actor_issuer=issuer)
        with pg.psycopg.connect(pg.db_url) as db:
            for name in ("014_hitl_reject_terminal_receipts.sql",
                         "015_core_run_event_idempotency.sql"):
                db.execute((fixture.MIG / name).read_text())
            db.execute("insert into aiops.incidents(incident_id,title,severity,state,"
                       "opened_at,source,synthetic,payload) values"
                       "(%s,'Worker graph005 CI','P4','OPEN',now(),%s,true,%s::jsonb)",
                       (incident, fixture.SOURCE, json.dumps({"tenant_id": tenant})))
            db.execute("insert into aiops.runs(run_id,incident_id,mode,scenario_id,"
                       "status,idempotency_key) values(%s,%s,'DEMO','GRAPH005-WORKER',"
                       "'CREATED','graph005-worker-unique')", (run, incident))
            for kind, rid in (("incident", incident), ("run", run),
                              ("glpi_instance", "GLPI-W"),
                              ("glpi_ticket", "GLPI-W:777"),
                              ("glpi_entity", "GLPI-W:33")):
                db.execute("insert into aiops.tenant_resource_ownership"
                           "(resource_kind,resource_id,tenant_id,source_event_id,"
                           "verified,observed_at,known_at) values"
                           "(%s,%s,%s,'CI-WORKER-OWN',true,"
                           "clock_timestamp()-interval '20 seconds',"
                           "clock_timestamp()-interval '10 seconds')",
                           (kind, rid, tenant))
            db.execute("insert into public.ci_actor_source_grants"
                       "(issuer,actor_subject,tenant_id,run_id,incident_id,"
                       "glpi_instance_id,ticket_id,glpi_entity_id,permission,"
                       "expires_at,revoked) values"
                       "(%s,%s,%s,%s,%s,'GLPI-W','777','33','run:read',"
                       "clock_timestamp()+interval '3 minutes',false)",
                       (issuer, actor, tenant, run, incident))
            for ordinal, (event_id, full_sha, payload_sha) in enumerate(expected, 1):
                payload = dict(tenant_id=tenant, incident_id=incident, run_id=run,
                    ticket_id="777", glpi_entity_id="33", source_event_id=event_id,
                    sequence=ordinal, actor_subject=actor, actor_issuer=issuer,
                    source_issuer=source_issuer, synthetic=True,
                    graph_version=pinned["graph_version"],
                    acme_full_event_sha256=full_sha,
                    acme_local_payload_sha256=payload_sha)
                provenance = dict(tenant_id=tenant, incident_id=incident, run_id=run,
                                  actor_subject=actor, actor_issuer=issuer,
                                  source_issuer=source_issuer)
                db.execute("insert into aiops.evidence"
                           "(evidence_id,source,external_id,observed_at,known_at,"
                           "claim,confidence,provenance,payload_hash,payload)"
                           " values(%s,%s,%s,clock_timestamp()-interval '20 seconds',"
                           "clock_timestamp()-interval '10 seconds','TEST_ONLY',1,"
                           "%s::jsonb,%s,%s::jsonb)",
                           (f"EVI-WORKER-{ordinal:02d}", fixture.SOURCE, event_id,
                            json.dumps(provenance), binding._digest(
                                binding.PAYLOAD_DOMAIN, payload), json.dumps(payload)))

        def snapshot():
            with pg.psycopg.connect(pg.db_url) as db:
                return {
                    "nonce_013": db.execute(
                        "select count(*) from aiops.actor_delegation_nonce_ledger").fetchone()[0],
                    "revocation_013": db.execute(
                        "select count(*) from aiops.actor_delegation_revocations").fetchone()[0],
                    "terminal_014": db.execute(
                        "select count(*) from aiops.hitl_reject_terminal_receipts").fetchone()[0],
                    "effects": db.execute("select count(*) from aiops.effect_receipts").fetchone()[0],
                    "approves": db.execute(
                        "select count(*) from aiops.hitl_decision_outbox "
                        "where decision='APPROVE'").fetchone()[0],
                }

        def read(req=scope, src=source_issuer):
            with pg.psycopg.connect(pg.db_url) as db:
                return source.read_graph005_core_written_seven(
                    db, req, source=fixture.SOURCE, issuer=src,
                    now=datetime.now(timezone.utc), expected_events=expected,
                    graph_version=pinned["graph_version"])

        def append_source(api, ordinal, version):
            event_id = expected[ordinal-1][0]
            with pg.psycopg.connect(pg.db_url) as db:
                payload = db.execute("select payload from aiops.evidence "
                    "where external_id=%s", (event_id,)).fetchone()[0]
            body = dict(expected_version=version, stage="SOURCE",
                        event_type="OBSERVED", status="PASS", event_key=event_id,
                        evidence_ids=[f"EVI-WORKER-{ordinal:02d}"], payload=payload)
            response = api.post(f"/api/runs/{run}/events", json=body,
                headers={"Authorization": "Bearer " + TOKEN})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertFalse(response.json()["idempotent"])
            self.assertEqual(response.json()["sequence"], version)
            return body

        workers = []
        async def launch(target, queue, tmp, stage, version):
            ready = tmp / (stage + ".ready")
            command = tmp / "reject.command" if stage == "VERIFY" else "-"
            done = tmp / "reject.done"
            env = dict(os.environ, AIOPS_INTERNAL_TOKEN=TOKEN, DATABASE_URL=pg.db_url)
            proc = subprocess.Popen([sys.executable, "-c", WORKER_CODE, pg.db_url,
                run, target, queue, str(ready), stage, str(version),
                str(command), str(done)], cwd=ROOT, env=env,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
            workers.append(proc)
            self.addCleanup(stop, proc)
            for _ in range(120):
                if proc.poll() is not None:
                    self.fail("independent_worker_process_exited")
                if ready.is_file():
                    return proc
                await asyncio.sleep(0.1)
            self.fail("independent_worker_process_not_ready")

        def stop(proc):
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)

        baseline = snapshot()
        self.assertEqual(baseline["effects"], 0)
        self.assertEqual(baseline["approves"], 0)
        with tempfile.TemporaryDirectory(prefix="worker-graph005-ci-") as root:
            tmp = Path(root)
            sqlite = str(tmp / "temporal.sqlite")
            queue = "worker-graph005-" + hashlib.sha256(os.urandom(24)).hexdigest()[:16]
            with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": TOKEN}), \
                    patch.object(main, "ADMIN", TOKEN), \
                    patch.object(main, "db", side_effect=lambda: pg.psycopg.connect(pg.db_url)):
                with TestClient(main.app) as api:
                    for ordinal in (1, 2):
                        append_source(api, ordinal, ordinal)
                    temporal_port_one = port()
                    async with await WorkflowEnvironment.start_local(
                            port=temporal_port_one, dev_server_database_filename=sqlite) as first:
                        handle = await first.client.start_workflow(
                            __import__("test_worker_hitl_reject_notification").SyntheticRejectSink.run,
                            id=queue, task_queue=queue)
                        worker_a = await launch(f"127.0.0.1:{temporal_port_one}",
                                                queue, tmp, "DGX_ANALYST", 3)
                        self.assertEqual(await handle.query(
                            __import__("test_worker_hitl_reject_notification").SyntheticRejectSink.count), 0)
                        for ordinal, version in ((3, 4), (4, 5), (5, 6)):
                            append_source(api, ordinal, version)
                        stop(worker_a)
                    self.assertTrue(Path(sqlite).is_file())
                    temporal_port_two = port()
                    async with await WorkflowEnvironment.start_local(
                            port=temporal_port_two, dev_server_database_filename=sqlite) as second:
                        handle = second.client.get_workflow_handle(queue)
                        worker_b = await launch(f"127.0.0.1:{temporal_port_two}",
                                                queue, tmp, "VERIFY", 7)
                        self.assertNotEqual(worker_a.pid, worker_b.pid)
                        for ordinal, version in ((6, 8), (7, 9)):
                            append_source(api, ordinal, version)
                        proof = read()
                        self.assertIsNotNone(proof)
                        self.assertEqual([x["sequence"] for x in proof["events"]],
                                         [1, 2, 4, 5, 6, 8, 9])
                        self.assertEqual([x["payload"]["sequence"] for x in proof["events"]],
                                         list(range(1, 8)))
                        self.assertIsNone(read({**scope, "actor_subject": "idp|forged"}))
                        self.assertIsNone(read(src="forged-source-issuer"))
                        (tmp / "reject.command").write_text("append")
                        for _ in range(120):
                            if (tmp / "reject.done").is_file():
                                break
                            self.assertIsNone(worker_b.poll())
                            await asyncio.sleep(0.1)
                        self.assertTrue((tmp / "reject.done").is_file())
                        self.assertIsNotNone(read())
                        with pg.psycopg.connect(pg.db_url) as db:
                            db.execute("update public.ci_actor_source_grants "
                                       "set revoked=true where run_id=%s", (run,))
                        self.assertIsNone(read())
                        replay_body = dict(expected_version=10, stage="HITL",
                            event_type="WORKFLOW_OBSERVATION", status="BLOCKED",
                            event_key="worker-graph005-reject", evidence_ids=[],
                            decision="REJECT", payload={"synthetic": True,
                            "reopen": "RECOMMENDED_NOT_EXECUTED",
                            "execution_allowed": False, "effect_allowed": False})
                        result = api.post(f"/api/runs/{run}/events", json=replay_body,
                            headers={"Authorization": "Bearer " + TOKEN})
                        self.assertEqual(result.status_code, 200, result.text)
                        self.assertTrue(result.json()["idempotent"])
                        self.assertIsNone(read())
                        self.assertEqual(await handle.query(
                            __import__("test_worker_hitl_reject_notification").SyntheticRejectSink.count), 0)
                        stop(worker_b)
                    with pg.psycopg.connect(pg.db_url) as db:
                        rows = db.execute("select sequence,stage,status,decision,payload "
                            "from aiops.run_events where run_id=%s order by sequence",
                            (run,)).fetchall()
                    self.assertEqual(len(rows), 10)
                    self.assertEqual([(r[0], r[1]) for r in rows if r[1] == "SOURCE"],
                                     [(i, "SOURCE") for i in (1, 2, 4, 5, 6, 8, 9)])
                    self.assertEqual((rows[6][1], rows[6][3]), ("VERIFY", "UNVERIFIED"))
                    self.assertEqual((rows[9][1], rows[9][3]), ("HITL", "REJECT"))
                    self.assertEqual(rows[9][4]["reopen"], "RECOMMENDED_NOT_EXECUTED")
                    self.assertEqual(snapshot(), baseline)
                    receipt = {
                        "schema": "aiops.worker-graph005-two-os-negative.v1",
                        "source_head": os.environ["AIOPS_EXPECTED_HEAD_SHA"],
                        "pg_major": 16, "source_ids": [e[0] for e in expected],
                        "source_physical_sequences": [1, 2, 4, 5, 6, 8, 9],
                        "source_ordinals": list(range(1, 8)),
                        "worker_os_processes": 2, "distinct_pids": True,
                        "temporal_server_persisted_restart": 1,
                        "temporal_signal_count": 0, "verification": "UNVERIFIED",
                        "hitl_event": "REJECT_BLOCKED_SYNTHETIC",
                        "core_terminal_014_exercised": False,
                        "core_outbox_replay_exercised": False,
                        "core_event_key_replay_idempotent": True,
                        "actor_source_revoked_before_replay": True,
                        "actor_source_revoked_after_replay": True,
                        "source_after_revocation": "UNKNOWN",
                        "reopen": "RECOMMENDED_NOT_EXECUTED",
                        "audit_013_014_unchanged": True, "effect_receipts": 0,
                        "approve_count": 0, "execution_allowed": False,
                        "effect_allowed": False, "human_glpi_attested": False,
                        "portable_signature": "NONE", "release_stable": "NO_GO",
                    }
                    receipt["payload_sha256"] = hashlib.sha256(json.dumps(
                        receipt, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                    out = Path(os.environ["AIOPS_CI_GRAPH005_RECEIPT_DIR"])
                    if not str(out).startswith("/tmp/worker-graph005-"):
                        raise RuntimeError("non_disposable_receipt_dir")
                    out.mkdir(parents=True, exist_ok=True)
                    (out / "two-os-negative.json").write_text(
                        json.dumps(receipt, sort_keys=True, indent=2) + "\n")
        for proc in workers:
            stop(proc)


if __name__ == "__main__":
    unittest.main()
