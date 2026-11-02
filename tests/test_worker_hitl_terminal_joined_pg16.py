"""Joined disposable Core #344 PG16 and *registered* production Worker activity.

Two independent OS Worker pollers; real local Temporal server persisted across
restart. Core owns 014 DEAD and 015 migration. Synthetic service actor ONLY:
never a human GLPI/IdP ALLOW, never a LIVE/GLPI write.
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

# unittest discovery prepends Worker tests; force Core #344's pinned fixture.
sys.path.insert(0, str(Path(os.environ['AIOPS_CORE344_ROOT']) / 'tests'))

import psycopg
import requests
from temporalio.testing import WorkflowEnvironment
from temporalio.client import WorkflowFailureError

import test_core_hitl_reject_terminal_pg16 as core_fixture
from worker.main import TerminalRejectWorkflow

WORKER = """
import asyncio, os, sys
from pathlib import Path
from temporalio.client import Client
from temporalio.worker import Worker
from worker.main import (IncidentWorkflow, TerminalRejectWorkflow,
    execute_stage, start_run, finish_run, reject_terminal_recover)
async def serve():
    client = await Client.connect(os.environ['TEMPORAL_ADDRESS'])
    async with Worker(client, task_queue='aiops-runner',
        workflows=[IncidentWorkflow, TerminalRejectWorkflow],
        activities=[execute_stage, start_run, finish_run, reject_terminal_recover]):
        Path(sys.argv[1]).write_text(str(os.getpid()))
        await asyncio.Event().wait()
asyncio.run(serve())
"""


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def stop(proc):
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


@unittest.skipUnless(
    os.getenv("GITHUB_ACTIONS") == "true"
    and os.getenv("AIOPS_XREF_CI_DISPOSABLE") == "1"
    and os.getenv("AIOPS_WORKER_CORE344_JOINED") == "YES",
    "requires explicitly disposable PG16 and Temporal CI")
class RegisteredTerminalCore344Joined(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.pg = core_fixture.CoreTerminalPopulatedPG16
        cls.pg.setUpClass()
        cls.fixture = cls.pg(methodName="test_terminal_atomic_and_ack_replay_denied")
        cls.fixture.setUp()
        # Apply 015 to the same isolated PG16 DB, not the host or shared DB.
        root = Path(core_fixture.__file__).resolve().parents[1]
        with psycopg.connect(cls.pg.url) as db:
            db.execute((root / "db/migrations/015_core_run_event_idempotency.sql").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.pg.tearDownClass()

    async def launch(self, argv, env, ready):
        proc = subprocess.Popen(argv, env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(stop, proc)
        for _ in range(150):
            if proc.poll() is not None:
                self.fail("joined_service_process_exited")
            if ready():
                return proc
            await asyncio.sleep(0.1)
        self.fail("joined_service_not_ready")

    async def test_registered_activity_core_dead_restart_replay_and_revocation(self):
        pg, fixture = self.pg, self.fixture
        ids, proposal_hash, tokens = fixture._exhaust()
        self.assertEqual(len(tokens), 8)  # tokens stay in Core fixture, never Worker args
        args = dict(tenant_id="TEN-A", event_id=ids["event"], run_id=ids["run"],
                    incident_id=ids["inc"], proposal_id=ids["proposal"],
                    proposal_hash=proposal_hash, proposal_revision=1,
                    decision="REJECT", execution_allowed=False, effect_allowed=False)
        body = dict(owner="svc-TEN-A", run_id=ids["run"],
                    incident_id=ids["inc"], proposal_id=ids["proposal"],
                    proposal_hash=proposal_hash, proposal_revision=1,
                    execution_allowed=False, effect_allowed=False)
        def entry(token, actor, tenant):
            return dict(token_sha256=hashlib.sha256(token.encode()).hexdigest(),
                        actor_id=actor, tenant_ids=[tenant],
                        permissions=["hitl:reject:deliver", "hitl:reject:terminal",
                                     "hitl:reject:recover"])
        manifest = json.dumps([entry(pg.token_a, "svc-TEN-A", "TEN-A"),
                               entry(pg.token_b, "svc-TEN-B", "TEN-B")])
        core_port = free_port()
        base = f"http://127.0.0.1:{core_port}"
        root = f"/api/tenants/TEN-A/hitl/reject-delivery/{ids['event']}"
        env = dict(os.environ, DATABASE_URL=pg.url,
                   AIOPS_INTERNAL_TOKEN=pg.token_a,
                   AIOPS_XREF_READ_AUTHZ_JSON=manifest,
                   AIOPS_REJECT_TERMINAL_OWNER="svc-TEN-A",
                   CORE_URL=base)
        with tempfile.TemporaryDirectory(prefix="worker-core344-joined-") as directory:
            tmp = Path(directory)
            core = await self.launch(
                [sys.executable, "-m", "uvicorn", "core.main:app",
                 "--host", "127.0.0.1", "--port", str(core_port)], env,
                lambda: self._core_ready(base))
            self.assertIsNone(core.poll())
            def post(bearer, suffix):
                return requests.post(base + root + suffix, json=body,
                    headers={"Authorization": "Bearer " + bearer}, timeout=10)
            self.assertEqual(post("invalid", "/terminal-recover").status_code, 401)
            self.assertEqual(post(pg.token_b, "/terminal-recover").status_code, 403)
            self.assertEqual(post(pg.token_a, "/terminal-receipt").json()["status"], "UNKNOWN")
            sqlite = str(tmp / "temporal.sqlite")
            pids = []
            signal_count = 0
            async def worker(target, index):
                ready = tmp / f"worker-{index}.ready"
                child_env = dict(env, TEMPORAL_ADDRESS=target)
                proc = await self.launch(
                    [sys.executable, "-c", WORKER, str(ready)], child_env,
                    lambda: ready.is_file())
                pids.append(int(ready.read_text()))
                return proc
            async def execute(client, name, expect_success):
                handle = await client.start_workflow(
                    TerminalRejectWorkflow.run, args,
                    id=f"core344-joined-{name}-{ids['event']}",
                    task_queue="aiops-runner")
                if expect_success:
                    result = await asyncio.wait_for(handle.result(), timeout=70)
                    self.assertEqual(result["status"], "DEAD")
                    self.assertFalse(result["temporal_signal_sent"])
                    self.assertFalse(result["ack_sent"])
                    self.assertFalse(result["effect_allowed"])
                    self.assertEqual(result["human_glpi_authorization"], "UNKNOWN")
                else:
                    with self.assertRaises(WorkflowFailureError):
                        await asyncio.wait_for(handle.result(), timeout=70)
                    result = None
                history = await handle.fetch_history()
                nonlocal signal_count
                signal_count += sum("SIGNALED" in str(e.event_type) for e in history.events)
                return result
            first_port = free_port()
            async with await WorkflowEnvironment.start_local(
                    port=first_port, dev_server_database_filename=sqlite) as first:
                proc_a = await worker(f"127.0.0.1:{first_port}", 1)
                initial = await execute(first.client, "initial", True)
                self.assertFalse(initial["idempotent"])
                stop(proc_a)
            self.assertTrue(Path(sqlite).is_file(), "Temporal persistence missing")
            second_port = free_port()
            async with await WorkflowEnvironment.start_local(
                    port=second_port, dev_server_database_filename=sqlite) as second:
                proc_b = await worker(f"127.0.0.1:{second_port}", 2)
                replay = await execute(second.client, "replay", True)
                self.assertTrue(replay["idempotent"])
                self.assertEqual(replay["receipt_sha256"], initial["receipt_sha256"])
                # Revocation of the independently signed Core source proof:
                # a committed 014 DEAD is still durable but no longer readable.
                Path(pg.proof_path).write_text(json.dumps({
                    "schema": "aiops.core-ownership-proof.v1", "proofs": {}}))
                self.assertEqual(post(pg.token_a, "/terminal-receipt").json()["status"],
                                 "UNKNOWN")
                await execute(second.client, "revoked", False)
                stop(proc_b)
            self.assertEqual(len(set(pids)), 2)
            self.assertEqual(signal_count, 0)
            with psycopg.connect(pg.url) as db:
                state = db.execute(
                    "select status,attempts from aiops.hitl_decision_outbox "
                    "where event_id=%s", (ids["event"],)).fetchone()
                audits = db.execute(
                    "select count(*) from aiops.hitl_reject_terminal_receipts "
                    "where event_id=%s", (ids["event"],)).fetchone()[0]
                effects = db.execute("select count(*) from aiops.effect_receipts").fetchone()[0]
                approves = db.execute(
                    "select count(*) from aiops.hitl_decision_outbox "
                    "where decision='APPROVE'").fetchone()[0]
                run_events = db.execute(
                    "select count(*) from aiops.run_events where run_id=%s",
                    (ids["run"],)).fetchone()[0]
            self.assertEqual(state, ("DEAD", 8))
            self.assertEqual((audits, effects, approves, run_events), (1, 0, 0, 0))
            fixture._no_effect()
            receipt = {
                "schema": "aiops.worker-core344-registered-joined.v1",
                "worker_head": os.environ["AIOPS_EXPECTED_HEAD_SHA"],
                "core_head": os.environ["AIOPS_CORE344_HEAD_SHA"],
                "worker_os_processes": 2, "distinct_pids": True,
                "temporal_persisted_restarts": 1,
                "production_registered_activity": "reject_terminal_recover",
                "core_http_recover": "200_DEAD",
                "core_http_readback": "200_DEAD_IDEMPOTENT",
                "core_pg16_014_rows": audits, "core_pg16_015_migration": True,
                "core_pg16_run_event_count": run_events,
                "core_outbox_status": state[0], "core_outbox_attempts": state[1],
                "core_replay_idempotent": True,
                "post_dead_source_revoked": "UNKNOWN",
                "unauthorized_bearer": 401, "wrong_tenant": 403,
                "temporal_signal_count": signal_count,
                "approve_count": approves, "effect_receipts": effects,
                "human_glpi_allow": False, "human_identity_attested": False,
                "live_effect": False, "glpi_write": False,
                "same_run_015_event_writer_joined": False,
                "debian_deployed": False, "release_stable": "NO_GO",
                "rollback": "REVERT_WORKER_TEST_WORKFLOW_ONLY"
            }
            receipt["payload_sha256"] = hashlib.sha256(json.dumps(
                receipt, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            output = Path(os.environ["AIOPS_WORKER_CORE344_RECEIPT_DIR"])
            output.mkdir(parents=True, exist_ok=True)
            (output / "worker-core344-joined.json").write_text(
                json.dumps(receipt, sort_keys=True, indent=2) + "\n")

    @staticmethod
    def _core_ready(base):
        try:
            return requests.get(base + "/openapi.json", timeout=0.5).status_code == 200
        except requests.RequestException:
            return False


if __name__ == "__main__":
    unittest.main()
