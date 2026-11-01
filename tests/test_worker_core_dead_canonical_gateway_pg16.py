"""Canonical Core HTTP /dead gateway replay; synthetic disposable Worker-owned test.

Core owns terminal transition and immutable migration 014 receipt. This test
never mutates DEAD with SQL, never emits Temporal signals and never grants
APPROVE, execution or effects. A deterministic gateway-close is NOT packet loss.
"""
import asyncio
import hashlib
import json
import os
import secrets
import socket
import subprocess
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import httpx
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

import test_worker_core_dead_positive_pg16 as positive
import test_worker_core_pg16_temporal_combined as base
from test_worker_hitl_reject_notification import SyntheticRejectSink


@unittest.skipUnless(
    os.getenv("GITHUB_ACTIONS") == "true"
    and os.getenv("AIOPS_CI_COMBINED_DISPOSABLE") == "YES"
    and os.getenv("AIOPS_CI_CORE_DEAD_POSITIVE") == "YES"
    and os.getenv("AIOPS_CI_CANONICAL_DEAD_GATEWAY") == "YES",
    "requires isolated disposable PG16 and persisted Temporal CI",
)
class CanonicalCoreDeadGatewayReplay(positive.CoreDeadPositiveWorkerContract):
    # Do not rerun the inherited positive test or any historical SQL DEAD case.
    test_11_core_owned_dead_after_eighth_expired_lease_and_replay = None

    async def test_12_canonical_core_dead_after_commit_gateway_close(self):
        head = os.environ["AIOPS_EXPECTED_HEAD_SHA"]
        self.assertEqual(len(head), 40)
        deliver_only = secrets.token_urlsafe(32)

        def principal(token, permissions):
            return {
                "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
                "actor_id": base.OWNER, "tenant_ids": [base.TENANT],
                "permissions": permissions,
            }

        authz = json.dumps([
            principal(self.bearer, ["hitl:reject:deliver",
                                    "hitl:reject:terminal"]),
            principal(deliver_only, ["hitl:reject:deliver"]),
        ])

        def free_port():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", 0))
                return sock.getsockname()[1]

        def body(item):
            # Exact eight-field Core ACK and /dead contract.
            return {
                "owner": base.OWNER, "run_id": item["run_id"],
                "proposal_id": item["proposal_id"],
                "proposal_hash": item["proposal_hash"],
                "proposal_revision": item["proposal_revision"],
                "lease_token": item["lease_token"],
                "execution_allowed": False, "effect_allowed": False,
            }

        core = gateway = upstream = gateway_thread = None
        with patch.dict(os.environ, {"AIOPS_XREF_READ_AUTHZ_JSON": authz}):
            def exhaust(ids):
                latest = None
                for attempt in range(8):
                    code, claim = self._claim()
                    self.assertEqual((code, claim["status"]), (200, "LEASED"))
                    self.assertEqual(len(claim["items"]), 1)
                    latest = claim["items"][0]
                    self.assertEqual(latest["event_id"], ids["event"])
                    self.assertEqual(latest["decision"], "REJECT")
                    self.assertIs(latest["execution_allowed"], False)
                    self.assertIs(latest["effect_allowed"], False)
                    # Accelerate lease time only; never SQL-inject DEAD.
                    with self.psycopg.connect(self.url) as db:
                        db.execute(
                            "update aiops.hitl_decision_outbox "
                            "set lease_until=now()-interval '2 seconds' "
                            "where event_id=%s and status='LEASED'",
                            (ids["event"],))
                with self.psycopg.connect(self.url) as db:
                    self.assertEqual(db.execute(
                        "select status,attempts from aiops.hitl_decision_outbox "
                        "where event_id=%s", (ids["event"],)).fetchone(),
                        ("LEASED", 8))
                self.assertEqual(self._claim()[1]["items"], [])
                return latest

            first = self._fixture()
            self._write_synthetic_proofs()
            lease_a = exhaust(first)
            second = self._fixture()
            self._write_synthetic_proofs()
            lease_b = exhaust(second)
            self.assertNotEqual(first["event"], second["event"])

            port = free_port()
            script = (
                "import uvicorn\n"
                "from core.main import app\n"
                f"uvicorn.run(app,host='127.0.0.1',port={port},"
                "access_log=False,log_level='error')\n"
            )
            core = subprocess.Popen(
                [sys.executable, "-c", script],
                cwd=str(base.ROOT),
                env=dict(os.environ, DATABASE_URL=self.url,
                         AIOPS_INTERNAL_TOKEN=secrets.token_urlsafe(32)),
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                for _ in range(100):
                    self.assertIsNone(core.poll(), "canonical Core TCP failed")
                    try:
                        with socket.create_connection(("127.0.0.1", port), 0.1):
                            break
                    except OSError:
                        await asyncio.sleep(0.1)
                else:
                    self.fail("canonical Core TCP not ready")

                upstream = httpx.Client(
                    base_url=f"http://127.0.0.1:{port}",
                    timeout=10.0, trust_env=False)
                route = ("/api/tenants/{tenant_id}/hitl/"
                         "reject-delivery/{event_id}/dead")
                self.assertIn(route, upstream.get("/openapi.json").json()["paths"])
                gateway = ThreadingHTTPServer(
                    ("127.0.0.1", 0), positive.TerminalResponseClose)
                gateway.upstream = upstream
                gateway.drop_once = True
                gateway.dropped = None
                gateway_thread = threading.Thread(
                    target=gateway.serve_forever, daemon=True)
                gateway_thread.start()

                async with httpx.AsyncClient(
                    base_url=f"http://127.0.0.1:{gateway.server_port}",
                    timeout=10.0, trust_env=False) as client:
                    async def post(path, payload, bearer=None):
                        response = await client.post(
                            path, json=payload,
                            headers={"Authorization": "Bearer " +
                                     (bearer or self.bearer)})
                        data = response.json()
                        self.assertIs(data["execution_allowed"], False)
                        self.assertIs(data["effect_allowed"], False)
                        return response.status_code, data

                    path_a = (f"/api/tenants/{base.TENANT}/hitl/"
                              f"reject-delivery/{first['event']}/dead")
                    path_b = (f"/api/tenants/{base.TENANT}/hitl/"
                              f"reject-delivery/{second['event']}/dead")

                    # Delivery permission alone is never terminal authority.
                    code, denied = await post(path_a, body(lease_a),
                                              deliver_only)
                    self.assertEqual((code, denied["status"]),
                                     (403, "UNKNOWN"))
                    forged = body(lease_a)
                    forged["lease_token"] = secrets.token_urlsafe(32)
                    code, denied = await post(path_a, forged)
                    self.assertEqual(denied["status"], "UNKNOWN")
                    code, denied = await post(
                        f"/api/tenants/TEN-OTHER/hitl/reject-delivery/"
                        f"{first['event']}/dead", body(lease_a))
                    self.assertEqual((code, denied["status"]),
                                     (403, "UNKNOWN"))

                    queue = "ci-canonical-dead-" + secrets.token_hex(8)
                    sqlite = str(Path(self.temp.name) / (queue + ".sqlite"))
                    async with await WorkflowEnvironment.start_local(
                        port=free_port(),
                        dev_server_database_filename=sqlite) as env:
                        handle = await env.client.start_workflow(
                            SyntheticRejectSink.run, id=queue, task_queue=queue)
                        async with Worker(env.client, task_queue=queue,
                                          workflows=[SyntheticRejectSink]):
                            self.assertEqual(
                                await handle.query(SyntheticRejectSink.count), 0)
                            # Core commits 014 before gateway closes downstream.
                            with self.assertRaises(httpx.TransportError):
                                await post(path_a, body(lease_a))
                            self.assertEqual(gateway.dropped, {
                                "status": "DEAD",
                                "event_id": first["event"],
                                "idempotent": False,
                            })
                            self.assertEqual(
                                await handle.query(SyntheticRejectSink.count), 0)

                    # Stop and restart actual Temporal server using same SQLite.
                    async with await WorkflowEnvironment.start_local(
                        port=free_port(),
                        dev_server_database_filename=sqlite) as restarted:
                        handle = restarted.client.get_workflow_handle(queue)
                        async with Worker(restarted.client, task_queue=queue,
                                          workflows=[SyntheticRejectSink]):
                            code, replay_a = await post(path_a, body(lease_a))
                            self.assertEqual(
                                (code, replay_a["status"],
                                 replay_a["idempotent"]),
                                (200, "DEAD", True))
                            code, dead_b = await post(path_b, body(lease_b))
                            self.assertEqual(
                                (code, dead_b["status"], dead_b["idempotent"]),
                                (200, "DEAD", False))
                            code, replay_b = await post(path_b, body(lease_b))
                            self.assertEqual(
                                (code, replay_b["status"],
                                 replay_b["idempotent"]),
                                (200, "DEAD", True))
                            for ids, lease in ((first, lease_a),
                                               (second, lease_b)):
                                code, stale = await post(
                                    f"/api/tenants/{base.TENANT}/hitl/"
                                    f"reject-delivery/{ids['event']}/ack",
                                    body(lease))
                                self.assertEqual(stale["status"], "UNKNOWN")
                            self.assertEqual(
                                await handle.query(SyntheticRejectSink.count), 0)

                snapshots = []
                with self.psycopg.connect(self.url) as db:
                    for ids, response in ((first, replay_a),
                                          (second, replay_b)):
                        rows = db.execute(
                            "select o.status,o.attempts,o.decision,"
                            "t.tenant_id,t.run_id,t.receipt_payload,"
                            "t.receipt_sha256 "
                            "from aiops.hitl_decision_outbox o "
                            "join aiops.hitl_reject_terminal_receipts t "
                            "on t.event_id=o.event_id "
                            "where o.event_id=%s", (ids["event"],)).fetchall()
                        self.assertEqual(len(rows), 1)
                        status, attempts, decision, tenant, run, audit, digest = rows[0]
                        self.assertEqual((status, attempts, decision, tenant, run),
                                         ("DEAD", 8, "REJECT", base.TENANT,
                                          ids["run"]))
                        self.assertIs(audit["execution_allowed"], False)
                        self.assertIs(audit["effect_allowed"], False)
                        self.assertEqual(audit["decision"], "REJECT")
                        canonical = json.dumps(
                            audit, sort_keys=True, separators=(",", ":"),
                            ensure_ascii=True).encode()
                        self.assertEqual(
                            hashlib.sha256(canonical).hexdigest(), digest)
                        self.assertEqual(response["receipt_sha256"], digest)
                        snapshots.append({
                            "event_id": ids["event"], "status": status,
                            "attempts": attempts, "decision": decision,
                            "audit_rows": 1, "receipt_sha256": digest,
                        })
                    self.assertEqual(db.execute(
                        "select count(*) from aiops.hitl_decision_outbox "
                        "where event_id=any(%s) and status='DELIVERED'",
                        ([first["event"], second["event"]],)).fetchone()[0], 0)
                self._no_effect()
                receipt = {
                    "schema": "aiops.worker-canonical-dead-gateway-replay.v1",
                    "source_head": head,
                    "environment": "CI_DISPOSABLE_SYNTHETIC_ONLY",
                    "core_http": "CANONICAL_CORE_MAIN_TCP_OBSERVED",
                    "migration_014": "CORE_OWNED_RUNTIME_OBSERVED",
                    "events": snapshots,
                    "event_count": 2, "dead_count": 2,
                    "audit_row_count": 2,
                    "gateway_close": "INJECTED_AFTER_CORE_TCP_DEAD_COMMIT",
                    "gateway_replay_idempotent": True,
                    "temporal_persisted_restarts": 1,
                    "temporal_signal_count": 0, "approve_count": 0,
                    "delivered_count": 0, "effect_receipt_count": 0,
                    "execution_allowed": False, "effect_allowed": False,
                    "terminal_permission_separate": True,
                    "stale_ack_rejected_count": 2,
                    "sql_dead_injection": False,
                    "lease_expiry": "CI_SQL_TIME_ACCELERATION_ONLY",
                    "physical_packet_loss": "NOT_TESTED",
                    "oidc_glpi_identity": "NOT_ATTESTED",
                    "host_7777": "NOT_VERIFIED",
                    "universal_exactly_once": "NOT_CLAIMED",
                }
                canonical = json.dumps(
                    receipt, sort_keys=True, separators=(",", ":")).encode()
                receipt["payload_sha256"] = hashlib.sha256(canonical).hexdigest()
                target = Path(os.environ["AIOPS_CI_CANONICAL_DEAD_RECEIPT_DIR"])
                if not str(target).startswith("/tmp/hitl-core-dead-canonical-"):
                    raise RuntimeError("non_disposable_receipt_path")
                target.mkdir(parents=True, exist_ok=True)
                (target / "canonical-dead-gateway.json").write_text(
                    json.dumps(receipt, sort_keys=True, indent=2) + "\n")
            finally:
                if gateway is not None:
                    gateway.shutdown()
                    gateway.server_close()
                if gateway_thread is not None:
                    gateway_thread.join(timeout=5)
                if upstream is not None:
                    upstream.close()
                if core is not None:
                    core.terminate()
                    try:
                        core.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        core.kill()
                        core.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
