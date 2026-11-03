"""Disposable positive ACME Temporal history survives restart on the SAME Run.

Real registered production activity and two OS Worker pollers, independent
authenticated loopback Core/Twin/Policy HTTP readbacks. Those readbacks are
synthetic fixtures, NOT Core PG16 terminal 018/019 or a Debian E2E proof.
"""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest

from temporalio.client import WorkflowAlreadyStartedError, WorkflowFailureError
from temporalio.common import WorkflowIDReusePolicy
from temporalio.testing import WorkflowEnvironment

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from worker.acme_simulated_hitl import receipt_digest_valid
from worker.temporal_workflows import AcmeSimulatedHitlWorkflow
from test_worker_acme_simulated_hitl import INTENT, fixtures

WORKER_PROCESS = """
import asyncio, os, sys
from pathlib import Path
from temporalio.client import Client
from temporalio.worker import Worker
from worker.main import acme_simulated_no_effect
from worker.temporal_workflows import AcmeSimulatedHitlWorkflow
async def main():
    client = await Client.connect(os.environ["TEMPORAL_ADDRESS"])
    async with Worker(client, task_queue="aiops-runner",
                      workflows=[AcmeSimulatedHitlWorkflow],
                      activities=[acme_simulated_no_effect]):
        Path(sys.argv[1]).write_text(str(os.getpid()))
        await asyncio.Event().wait()
asyncio.run(main())
"""


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


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
    "requires disposable Temporal CI")
class PositiveAcmeTemporalPersistedRestart(unittest.IsolatedAsyncioTestCase):
    async def test_same_run_positive_history_restart_replay_and_denials(self):
        now = datetime.now(timezone.utc)
        docs = fixtures()
        docs["twin"]["issued_at"] = (now - timedelta(seconds=15)).isoformat()
        docs["twin"]["expires_at"] = (now + timedelta(minutes=4)).isoformat()
        token = "ci-acme-temporal-synthetic-bearer-32chars"
        seen = []
        servers = []
        threads = []
        lock = threading.Lock()

        def handler(component):
            class Readback(BaseHTTPRequestHandler):
                def do_GET(self):
                    with lock:
                        seen.append((component, self.path,
                                     self.headers.get("Authorization")))
                        payload = deepcopy(docs[component])
                    if (self.path != "/api/sandbox/acme/e2e/" + INTENT["attempt_id"]
                            or self.headers.get("Authorization") != "Bearer " + token):
                        self.send_response(401)
                        self.end_headers()
                        return
                    body = json.dumps(payload).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

                def log_message(self, *_args):
                    pass
            return Readback

        for component, port in (("core", 810), ("twin", 811), ("policy", 813)):
            server = ThreadingHTTPServer(("127.0.0.1", port), handler(component))
            server.daemon_threads = True
            thread = threading.Thread(target=server.serve_forever,
                                      kwargs={"poll_interval": 0.05}, daemon=True)
            thread.start()
            servers.append(server)
            threads.append(thread)

        def cleanup_servers():
            for server in servers:
                server.shutdown()
                server.server_close()
            for thread in threads:
                thread.join(timeout=5)
        self.addCleanup(cleanup_servers)

        with tempfile.TemporaryDirectory(prefix="acme-temporal-persisted-") as directory:
            tmp = Path(directory)
            netrc = tmp / "hostile.netrc"
            netrc.write_text("machine 127.0.0.1 login hostile password hostile\n")
            netrc.chmod(0o600)
            env = dict(os.environ,
                AIOPS_ACME_SANDBOX_ENABLED="true",
                AIOPS_INTERNAL_TOKEN=token,
                CORE_URL="http://127.0.0.1:810",
                TWIN_URL="http://127.0.0.1:811",
                POLICY_URL="http://127.0.0.1:813",
                HTTP_PROXY="http://127.0.0.1:1",
                HTTPS_PROXY="http://127.0.0.1:1",
                ALL_PROXY="http://127.0.0.1:1",
                NO_PROXY="",
                NETRC=str(netrc),
                PYTHONPATH=str(Path(__file__).resolve().parents[1] / "app")
                    + os.pathsep + os.environ.get("PYTHONPATH", ""))
            sqlite = str(tmp / "temporal.sqlite")
            workflow_id = "acme-simulated-ACME-TEST-" + INTENT["attempt_id"]
            pids = []

            async def start_worker(target, number):
                ready = tmp / f"worker-{number}.ready"
                child_env = dict(env, TEMPORAL_ADDRESS=target)
                proc = subprocess.Popen(
                    [sys.executable, "-c", WORKER_PROCESS, str(ready)],
                    env=child_env, stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                self.addCleanup(stop, proc)
                for _ in range(150):
                    if proc.poll() is not None:
                        stderr = proc.communicate(timeout=2)[1].decode(
                            "utf-8", "replace").replace(token, "[REDACTED]")
                        self.fail("registered_acme_worker_exited:" + stderr[-1500:])
                    if ready.is_file():
                        pids.append(int(ready.read_text()))
                        return proc
                    await asyncio.sleep(0.1)
                self.fail("registered_acme_worker_not_ready")

            first_port = free_port()
            async with await WorkflowEnvironment.start_local(
                    port=first_port, dev_server_database_filename=sqlite) as first:
                worker_a = await start_worker(f"127.0.0.1:{first_port}", 1)
                handle = await first.client.start_workflow(
                    AcmeSimulatedHitlWorkflow.run, INTENT, id=workflow_id,
                    task_queue="aiops-runner",
                    id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE)
                initial = await asyncio.wait_for(handle.result(), timeout=60)
                self.assertTrue(receipt_digest_valid(initial))
                self.assertEqual(initial["run_id"], INTENT["run_id"])
                self.assertEqual(initial["receipt_status"], "SIMULATED_NO_EFFECT")
                self.assertEqual(initial["effect_receipts"], 0)
                self.assertFalse(initial["human_approved"])
                self.assertFalse(initial["execution_allowed"])
                self.assertFalse(initial["glpi_write"])
                stop(worker_a)
            self.assertTrue(Path(sqlite).is_file())

            second_port = free_port()
            async with await WorkflowEnvironment.start_local(
                    port=second_port, dev_server_database_filename=sqlite) as second:
                worker_b = await start_worker(f"127.0.0.1:{second_port}", 2)
                replay = await asyncio.wait_for(
                    second.client.get_workflow_handle(workflow_id).result(),
                    timeout=30)
                self.assertEqual(replay, initial)
                self.assertEqual(replay["receipt_sha256"], initial["receipt_sha256"])
                with self.assertRaises(WorkflowAlreadyStartedError):
                    await second.client.start_workflow(
                        AcmeSimulatedHitlWorkflow.run, INTENT, id=workflow_id,
                        task_queue="aiops-runner",
                        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE)

                with lock:
                    docs["policy"]["state"] = "BLOCKED"
                denied = await second.client.start_workflow(
                    AcmeSimulatedHitlWorkflow.run, INTENT,
                    id=workflow_id + "-policy-revoked", task_queue="aiops-runner")
                with self.assertRaises(WorkflowFailureError):
                    await asyncio.wait_for(denied.result(), timeout=60)
                with lock:
                    docs["policy"]["state"] = "PASS"
                    docs["twin"]["expires_at"] = (
                        datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
                expired = await second.client.start_workflow(
                    AcmeSimulatedHitlWorkflow.run, INTENT,
                    id=workflow_id + "-expired", task_queue="aiops-runner")
                with self.assertRaises(WorkflowFailureError):
                    await asyncio.wait_for(expired.result(), timeout=60)
                foreign = dict(INTENT, tenant_id="FOREIGN")
                cross_tenant = await second.client.start_workflow(
                    AcmeSimulatedHitlWorkflow.run, foreign,
                    id=workflow_id + "-foreign", task_queue="aiops-runner")
                with self.assertRaises(WorkflowFailureError):
                    await asyncio.wait_for(cross_tenant.result(), timeout=60)
                stop(worker_b)

            self.assertEqual(len(set(pids)), 2)
            self.assertEqual(len(seen), 12)
            self.assertEqual([x[0] for x in seen[:6]],
                             ["core", "twin", "policy", "core", "twin", "policy"])
            self.assertEqual([x[0] for x in seen[6:]],
                             ["core", "twin", "policy", "core", "twin", "policy"])
            self.assertTrue(all(path.endswith(INTENT["attempt_id"])
                                and auth == "Bearer " + token
                                for _, path, auth in seen))
            receipt = {
                "schema": "aiops.worker-acme-positive-temporal-restart.v1",
                "worker_head": os.environ["AIOPS_EXPECTED_HEAD_SHA"],
                "run_id": INTENT["run_id"], "incident_id": INTENT["incident_id"],
                "worker_os_processes": 2, "distinct_pids": True,
                "temporal_persisted_restarts": 1,
                "registered_activity": "acme_simulated_no_effect",
                "receipt_status": "SIMULATED_NO_EFFECT",
                "receipt_sha256": initial["receipt_sha256"],
                "same_run_history_digest_stable": True,
                "workflow_id_replay_rejected": True,
                "policy_revoked_denied": True,
                "expired_twin_denied": True,
                "cross_tenant_denied": True,
                "direct_only_bearer_gets": len(seen),
                "effect_receipts": 0, "human_glpi_allow": False,
                "live_effect": False, "glpi_write": False,
                "readbacks": "SYNTHETIC_AUTHENTICATED_LOOPBACK",
                "core_pg16_positive_same_run_joined": False,
                "host_deployed": False
            }
            receipt["payload_sha256"] = hashlib.sha256(json.dumps(
                receipt, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            output = Path(os.environ["AIOPS_WORKER_CORE344_RECEIPT_DIR"])
            output.mkdir(parents=True, exist_ok=True)
            (output / "worker-acme-positive-temporal-restart.json").write_text(
                json.dumps(receipt, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    unittest.main()
