"""Worker-owned positive Core /dead contract qualification; CI disposable only.

Core implements the transition and migration 014. This test NEVER mutates DEAD
through SQL, never signals Temporal, and never authorizes any effect or APPROVE.
Gateway-close after committed /dead is not physical packet loss.
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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import httpx
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

import test_worker_core_pg16_temporal_combined as base
from test_worker_hitl_reject_notification import SyntheticRejectSink


class TerminalResponseClose(BaseHTTPRequestHandler):
    """Close the downstream socket only AFTER independent Core TCP commits DEAD."""
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length < 1 or length > 8192:
            self.send_error(400)
            return
        body = self.rfile.read(length)
        upstream = self.server.upstream.post(
            self.path, content=body,
            headers={"Authorization": self.headers.get("Authorization", ""),
                     "Content-Type": "application/json"})
        data = upstream.json()
        if (self.path.endswith("/dead") and self.server.drop_once
                and upstream.status_code == 200 and data.get("status") == "DEAD"):
            self.server.drop_once = False
            self.server.dropped = {"status": "DEAD", "event_id": data["event_id"],
                                   "idempotent": data["idempotent"]}
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.close_connection = True
            return
        self.send_response(upstream.status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(upstream.content)))
        self.end_headers()
        self.wfile.write(upstream.content)


@unittest.skipUnless(
    os.getenv("GITHUB_ACTIONS") == "true"
    and os.getenv("AIOPS_CI_COMBINED_DISPOSABLE") == "YES"
    and os.getenv("AIOPS_CI_CORE_DEAD_POSITIVE") == "YES",
    "only disposable CI PostgreSQL16/Temporal environment")
class CoreDeadPositiveWorkerContract(base.CombinedCoreWorkerPG16):
    # Reuse the already qualified fixture and ownership HMAC. Do not re-run
    # inherited combined tests or their SQL-injected DEAD scenario.
    def setUp(self):
        pass

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            with cls.psycopg.connect(cls.url) as db:
                for name in ("013_actor_delegation_replay_ledger.sql",
                             "014_hitl_reject_terminal_receipts.sql"):
                    db.execute((base.ROOT / "db/migrations" / name).read_text())
                assert db.execute(
                    "select to_regclass('aiops.hitl_reject_terminal_receipts')"
                ).fetchone()[0] is not None
        except Exception:
            super().tearDownClass()
            raise

    async def test_11_core_owned_dead_after_eighth_expired_lease_and_replay(self):
        expected_head = os.environ["AIOPS_EXPECTED_HEAD_SHA"]
        self.assertEqual(len(expected_head), 40)
        delivery_only = secrets.token_urlsafe(32)
        def principal(token, permissions):
            return {
                "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
                "actor_id": base.OWNER, "tenant_ids": [base.TENANT],
                "permissions": permissions,
            }
        authz = json.dumps([
            principal(self.bearer, ["hitl:reject:deliver",
                                    "hitl:reject:terminal"]),
            principal(delivery_only, ["hitl:reject:deliver"]),
        ])
        core = gateway = upstream = gateway_thread = None
        with patch.dict(os.environ, {"AIOPS_XREF_READ_AUTHZ_JSON": authz}):
            first = self._fixture()
            self._write_synthetic_proofs()
            snapshots = []

            def exhaust(ids):
                latest = None
                for attempt in range(8):
                    code, result = self._claim()
                    self.assertEqual((code, result["status"]), (200, "LEASED"))
                    self.assertEqual(len(result["items"]), 1)
                    latest = result["items"][0]
                    self.assertEqual(latest["event_id"], ids["event"])
                    self.assertEqual(latest["decision"], "REJECT")
                    self.assertIs(latest["execution_allowed"], False)
                    self.assertIs(latest["effect_allowed"], False)
                    with self.psycopg.connect(self.url) as db:
                        db.execute(
                            "update aiops.hitl_decision_outbox "
                            "set lease_until=now()-interval '2 seconds' "
                            "where event_id=%s and status='LEASED'",
                            (ids["event"],))
                with self.psycopg.connect(self.url) as db:
                    state = db.execute(
                        "select status,attempts from aiops.hitl_decision_outbox "
                        "where event_id=%s", (ids["event"],)).fetchone()
                self.assertEqual(state, ("LEASED", 8))
                self.assertEqual(self._claim()[1]["items"], [])
                return latest

            lease_a = exhaust(first)
            second = self._fixture()
            self._write_synthetic_proofs()
            lease_b = exhaust(second)
            self.assertNotEqual(first["event"], second["event"])

            def body(item):
                # Exact eight-field ACK shape reused by Core /dead.
                return {"owner": base.OWNER, "run_id": item["run_id"],
                        "proposal_id": item["proposal_id"],
                        "proposal_hash": item["proposal_hash"],
                        "proposal_revision": item["proposal_revision"],
                        "lease_token": item["lease_token"],
                        "execution_allowed": False, "effect_allowed": False}

            def free_port():
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.bind(("127.0.0.1", 0))
                    return sock.getsockname()[1]

            port = free_port()
            script = (
                "from fastapi import FastAPI\n"
                "from core.hitl_reject_delivery import router\n"
                "import uvicorn\n"
                "app=FastAPI(); app.include_router(router)\n"
                f"uvicorn.run(app,host='127.0.0.1',port={port},"
                "access_log=False,log_level='error')\n")
            core = subprocess.Popen(
                [sys.executable, "-c", script], cwd=str(base.ROOT),
                env=dict(os.environ, DATABASE_URL=self.url),
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
            try:
                for _ in range(100):
                    self.assertIsNone(core.poll(), "independent Core TCP failed")
                    try:
                        with socket.create_connection(("127.0.0.1", port), 0.1):
                            break
                    except OSError:
                        await asyncio.sleep(0.1)
                else:
                    self.fail("independent Core TCP not ready")
                upstream = httpx.Client(
                    base_url=f"http://127.0.0.1:{port}",
                    timeout=10.0, trust_env=False)
                gateway = ThreadingHTTPServer(("127.0.0.1", 0),
                                              TerminalResponseClose)
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
                    code, denial = await post(path_a, body(lease_a),
                                              delivery_only)
                    self.assertEqual((code, denial["status"]), (403, "UNKNOWN"))
                    for field, value in (
                        ("lease_token", secrets.token_urlsafe(32)),
                        ("run_id", second["run"]),
                        ("proposal_hash", "f" * 64),
                        ("proposal_revision", 2),
                        ("owner", "svc-forged-owner"),
                        ("execution_allowed", True)):
                        altered = body(lease_a)
                        altered[field] = value
                        code, denial = await post(path_a, altered)
                        self.assertEqual(denial["status"], "UNKNOWN", field)
                    code, denial = await post(
                        f"/api/tenants/TEN-OTHER/hitl/reject-delivery/"
                        f"{first['event']}/dead", body(lease_a))
                    self.assertEqual((code, denial["status"]), (403, "UNKNOWN"))

                    # Gateway closes only after independent Core TCP committed
                    # the real 014 terminal receipt. This is not packet loss.
                    with self.assertRaises(httpx.TransportError):
                        await post(path_a, body(lease_a))
                    self.assertEqual(gateway.dropped,
                                     {"status": "DEAD",
                                      "event_id": first["event"],
                                      "idempotent": False})
                    code, replay = await post(path_a, body(lease_a))
                    self.assertEqual(
                        (code, replay["status"], replay["idempotent"]),
                        (200, "DEAD", True))
                    code, stale_ack = await post(
                        path_a[:-4] + "ack", body(lease_a))
                    self.assertEqual(stale_ack["status"], "UNKNOWN")

                    # Persisted Temporal server is stopped and started again.
                    # No signal is ever sent; the test Worker is notification-only.
                    queue = "ci-dead-no-signal-" + secrets.token_hex(8)
                    sqlite = str(Path(self.temp.name) / (queue + ".sqlite"))
                    temporal_port = free_port()
                    async with await WorkflowEnvironment.start_local(
                        port=temporal_port,
                        dev_server_database_filename=sqlite) as env:
                        handle = await env.client.start_workflow(
                            SyntheticRejectSink.run, id=queue, task_queue=queue)
                        async with Worker(env.client, task_queue=queue,
                                          workflows=[SyntheticRejectSink]):
                            self.assertEqual(
                                await handle.query(SyntheticRejectSink.count), 0)
                    temporal_port_two = free_port()
                    async with await WorkflowEnvironment.start_local(
                        port=temporal_port_two,
                        dev_server_database_filename=sqlite) as restarted:
                        handle = restarted.client.get_workflow_handle(queue)
                        async with Worker(restarted.client, task_queue=queue,
                                          workflows=[SyntheticRejectSink]):
                            self.assertEqual(
                                await handle.query(SyntheticRejectSink.count), 0)
                            code, result_b = await post(path_b, body(lease_b))
                            self.assertEqual(
                                (code, result_b["status"], result_b["idempotent"]),
                                (200, "DEAD", False))
                            code, replay_b = await post(path_b, body(lease_b))
                            self.assertEqual(
                                (code, replay_b["status"], replay_b["idempotent"]),
                                (200, "DEAD", True))
                            self.assertEqual(
                                await handle.query(SyntheticRejectSink.count), 0)

                    with self.psycopg.connect(self.url) as db:
                        for ids, result in ((first, replay), (second, result_b)):
                            row = db.execute(
                                "select o.status,o.attempts,o.decision,"
                                "t.receipt_payload,t.receipt_sha256 "
                                "from aiops.hitl_decision_outbox o "
                                "join aiops.hitl_reject_terminal_receipts t "
                                "on t.event_id=o.event_id where o.event_id=%s",
                                (ids["event"],)).fetchone()
                            self.assertIsNotNone(row)
                            status, attempts, decision, audit, digest = row
                            self.assertEqual((status, attempts, decision),
                                             ("DEAD", 8, "REJECT"))
                            self.assertEqual(audit["event_id"], ids["event"])
                            self.assertEqual(audit["decision"], "REJECT")
                            self.assertIs(audit["execution_allowed"], False)
                            self.assertIs(audit["effect_allowed"], False)
                            canonical = json.dumps(
                                audit, sort_keys=True, separators=(",", ":"),
                                ensure_ascii=True).encode()
                            self.assertEqual(
                                hashlib.sha256(canonical).hexdigest(), digest)
                            self.assertEqual(result["receipt_sha256"], digest)
                            snapshots.append({
                                "event_id": ids["event"], "run_id": ids["run"],
                                "status": status, "attempts": attempts,
                                "decision": decision, "receipt_sha256": digest,
                                "audit_rows": 1,
                            })
                        self.assertEqual(db.execute(
                            "select count(*) from aiops.hitl_reject_terminal_receipts "
                            "where event_id=any(%s)",
                            ([first["event"], second["event"]],)).fetchone()[0], 2)
                        self.assertEqual(db.execute(
                            "select count(*) from aiops.hitl_decision_outbox "
                            "where status='DELIVERED' and event_id=any(%s)",
                            ([first["event"], second["event"]],)).fetchone()[0], 0)
                    self._no_effect()
                    receipt = {
                        "schema": "aiops.worker-core-dead-positive.v1",
                        "source_head": expected_head,
                        "environment": "CI_DISPOSABLE_SYNTHETIC_ONLY",
                        "migration_014": "CORE_OWNED_RUNTIME_OBSERVED",
                        "events": snapshots,
                        "event_count": 2, "dead_count": 2,
                        "temporal_server_instances": 2,
                        "temporal_persisted_restarts": 1,
                        "temporal_signal_count": 0,
                        "approve_count": 0, "delivered_count": 0,
                        "effect_receipt_count": 0,
                        "execution_allowed": False, "effect_allowed": False,
                        "gateway_close": "INJECTED_AFTER_CORE_TCP_DEAD_COMMIT",
                        "physical_packet_loss": "NOT_TESTED",
                        "oidc_glpi_identity": "NOT_ATTESTED",
                        "universal_exactly_once": "NOT_CLAIMED",
                        "sql_dead_injection": False,
                        "lease_expiry": "CI_SQL_TIME_ACCELERATION_ONLY",
                    }
                    canonical = json.dumps(
                        receipt, sort_keys=True, separators=(",", ":")).encode()
                    receipt["payload_sha256"] = hashlib.sha256(canonical).hexdigest()
                    target = Path(os.environ["AIOPS_CI_COMBINED_RECEIPT_DIR"])
                    if not str(target).startswith("/tmp/hitl-core-dead-positive-"):
                        raise RuntimeError("non_disposable_receipt_path")
                    target.mkdir(parents=True, exist_ok=True)
                    (target / "core-dead-positive.json").write_text(
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


# Mask inherited cases, including historical CI_INJECTED_SQL DEAD case.
for _name in (name for name in dir(base.CombinedCoreWorkerPG16)
              if name.startswith("test_")):
    setattr(CoreDeadPositiveWorkerContract, _name, None)


if __name__ == "__main__":
    unittest.main()
