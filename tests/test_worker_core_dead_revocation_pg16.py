"""Worker-only negative revocation regression after canonical Core-owned DEAD.

CI disposable PG16 + Core TCP + persisted Temporal. No SQL DEAD mutation.
Synthetic ownership proof withdrawal is NOT a real GLPI/OIDC revocation.
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

import test_worker_core_dead_canonical_gateway_pg16 as previous
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
class CanonicalPostDeadRevocation(previous.CanonicalCoreDeadGatewayReplay):
    # Reuse Core-owned 013/014 migrations/fixtures; do not rerun older cases.
    test_11_core_owned_dead_after_eighth_expired_lease_and_replay = None
    test_12_canonical_core_dead_after_commit_gateway_close = None
    test_13_concurrent_postdead_retry_fencing_after_temporal_restart = None

    async def test_14_postdead_actor_and_tenant_provenance_revocation(self):
        head = os.environ["AIOPS_EXPECTED_HEAD_SHA"]
        self.assertEqual(len(head), 40)
        delivery_only = secrets.token_urlsafe(32)
        foreign_scoped = secrets.token_urlsafe(32)

        def principal(token, tenant, permissions):
            return {
                "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
                "actor_id": base.OWNER, "tenant_ids": [tenant],
                "permissions": permissions,
            }

        allowed = json.dumps([
            principal(self.bearer, base.TENANT,
                      ["hitl:reject:deliver", "hitl:reject:terminal"]),
            principal(delivery_only, base.TENANT, ["hitl:reject:deliver"]),
        ])
        revoked = json.dumps([
            principal(delivery_only, base.TENANT, ["hitl:reject:deliver"]),
            principal(foreign_scoped, "TEN-FOREIGN",
                      ["hitl:reject:deliver", "hitl:reject:terminal"]),
        ])

        def free_port():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", 0))
                return sock.getsockname()[1]

        def ack_body(lease):
            return {
                "owner": base.OWNER, "run_id": lease["run_id"],
                "proposal_id": lease["proposal_id"],
                "proposal_hash": lease["proposal_hash"],
                "proposal_revision": lease["proposal_revision"],
                "lease_token": lease["lease_token"],
                "execution_allowed": False, "effect_allowed": False,
            }

        def start_core(authz):
            port = free_port()
            script = (
                "import uvicorn\nfrom core.main import app\n"
                f"uvicorn.run(app,host='127.0.0.1',port={port},"
                "access_log=False,log_level='error')\n"
            )
            proc = subprocess.Popen(
                [sys.executable, "-c", script], cwd=str(base.ROOT),
                env=dict(os.environ, DATABASE_URL=self.url,
                         AIOPS_XREF_READ_AUTHZ_JSON=authz,
                         AIOPS_INTERNAL_TOKEN=secrets.token_urlsafe(32)),
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
            return proc, port

        async def wait_core(proc, port):
            for _ in range(100):
                self.assertIsNone(proc.poll(), "canonical Core TCP failed")
                try:
                    with socket.create_connection(("127.0.0.1", port), 0.1):
                        return
                except OSError:
                    await asyncio.sleep(0.1)
            self.fail("canonical Core TCP not ready")

        def stop_core(proc):
            if proc is not None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)

        def snapshot(event):
            with self.psycopg.connect(self.url) as db:
                rows = db.execute(
                    "select o.status,o.attempts,o.decision,"
                    "t.receipt_payload,t.receipt_sha256 "
                    "from aiops.hitl_decision_outbox o "
                    "join aiops.hitl_reject_terminal_receipts t "
                    "on t.event_id=o.event_id where o.event_id=%s",
                    (event,)).fetchall()
                self.assertEqual(len(rows), 1)
                status, attempts, decision, audit, digest = rows[0]
                self.assertEqual((status, attempts, decision),
                                 ("DEAD", 8, "REJECT"))
                self.assertIs(audit["execution_allowed"], False)
                self.assertIs(audit["effect_allowed"], False)
                canonical = json.dumps(
                    audit, sort_keys=True, separators=(",", ":"),
                    ensure_ascii=True).encode()
                self.assertEqual(hashlib.sha256(canonical).hexdigest(), digest)
                return digest

        core = gateway = upstream = gateway_thread = None
        with patch.dict(os.environ, {"AIOPS_XREF_READ_AUTHZ_JSON": allowed}):
            first = self._fixture()
            self._write_synthetic_proofs()
            lease = None
            for _ in range(8):
                code, result = self._claim()
                self.assertEqual((code, result["status"]), (200, "LEASED"))
                self.assertEqual(len(result["items"]), 1)
                lease = result["items"][0]
                self.assertEqual(lease["event_id"], first["event"])
                self.assertEqual(lease["decision"], "REJECT")
                self.assertIs(lease["execution_allowed"], False)
                self.assertIs(lease["effect_allowed"], False)
                # Only synthetic lease-clock acceleration; no status/DEAD SQL.
                with self.psycopg.connect(self.url) as db:
                    db.execute(
                        "update aiops.hitl_decision_outbox "
                        "set lease_until=now()-interval '2 seconds' "
                        "where event_id=%s and status='LEASED'",
                        (first["event"],))
            with self.psycopg.connect(self.url) as db:
                self.assertEqual(db.execute(
                    "select status,attempts from aiops.hitl_decision_outbox "
                    "where event_id=%s", (first["event"],)).fetchone(),
                    ("LEASED", 8))

            try:
                core, port = start_core(allowed)
                await wait_core(core, port)
                upstream = httpx.Client(
                    base_url=f"http://127.0.0.1:{port}",
                    timeout=15.0, trust_env=False)
                gateway = ThreadingHTTPServer(
                    ("127.0.0.1", 0), positive.TerminalResponseClose)
                gateway.upstream = upstream
                gateway.drop_once = True
                gateway.dropped = None
                gateway_thread = threading.Thread(
                    target=gateway.serve_forever, daemon=True)
                gateway_thread.start()
                path = (f"/api/tenants/{base.TENANT}/hitl/"
                        f"reject-delivery/{first['event']}")
                claim_path = (f"/api/tenants/{base.TENANT}/hitl/"
                              "reject-delivery/claim")
                queue = "ci-postdead-revocation-" + secrets.token_hex(8)
                sqlite = str(Path(self.temp.name) / (queue + ".sqlite"))
                async with httpx.AsyncClient(
                    base_url=f"http://127.0.0.1:{gateway.server_port}",
                    timeout=20.0, trust_env=False) as client:
                    async with await WorkflowEnvironment.start_local(
                        port=free_port(),
                        dev_server_database_filename=sqlite) as temporal:
                        handle = await temporal.client.start_workflow(
                            SyntheticRejectSink.run, id=queue, task_queue=queue)
                        async with Worker(temporal.client, task_queue=queue,
                                          workflows=[SyntheticRejectSink]):
                            with self.assertRaises(httpx.TransportError):
                                await client.post(
                                    path + "/dead", json=ack_body(lease),
                                    headers={"Authorization": "Bearer " +
                                             self.bearer})
                            self.assertEqual(gateway.dropped, {
                                "status": "DEAD", "event_id": first["event"],
                                "idempotent": False})
                            self.assertEqual(
                                await handle.query(SyntheticRejectSink.count), 0)

                before = snapshot(first["event"])
                # Second REJECT remains pending, so claim must examine
                # its revoked tenant ownership rather than merely find no work.
                second = self._fixture()
                self._write_synthetic_proofs()
                with self.psycopg.connect(self.url) as db:
                    self.assertEqual(db.execute(
                        "select status,attempts from aiops.hitl_decision_outbox "
                        "where event_id=%s", (second["event"],)).fetchone(),
                        ("PENDING", 0))
                    # The Core 012 provenance ledger is append-only.
                    # Never mutate its rows: withdraw only the CI-signed
                    # synthetic ownership proof manifest outside PostgreSQL.
                    self.assertEqual(db.execute(
                        "select count(*) from aiops.tenant_resource_ownership "
                        "where resource_kind='run' and resource_id=any(%s) "
                        "and verified=true",
                        ([first["run"], second["run"]],)).fetchone()[0], 2)
                Path(self.proof_path).write_text(json.dumps({
                    "schema": "aiops.core-ownership-proof.v1",
                    "proofs": {},
                }))
                self.assertEqual(json.loads(
                    Path(self.proof_path).read_text())["proofs"], {})

                # Phase 1: actor remains ACL-authorized, but synthetic
                # tenant/Run proof manifest is explicitly withdrawn.
                async with httpx.AsyncClient(
                    base_url=f"http://127.0.0.1:{gateway.server_port}",
                    timeout=20.0, trust_env=False,
                    limits=httpx.Limits(max_connections=24)) as client:
                    async def call(client, endpoint, payload, token):
                        response = await client.post(
                            endpoint, json=payload,
                            headers={"Authorization": "Bearer " + token})
                        data = response.json()
                        self.assertIs(data["execution_allowed"], False)
                        self.assertIs(data["effect_allowed"], False)
                        return response.status_code, data

                    n = 4
                    calls = (
                        [call(client, path + "/dead", ack_body(lease),
                              self.bearer) for _ in range(n)] +
                        [call(client, path + "/ack", ack_body(lease),
                              self.bearer) for _ in range(n)] +
                        [call(client, claim_path,
                              {"owner": base.OWNER, "limit": 1},
                              self.bearer) for _ in range(n)]
                    )
                    denied = await asyncio.gather(*calls)
                    for code, data in denied:
                        self.assertEqual(data["status"], "UNKNOWN")
                        self.assertNotIn("receipt_sha256", data)
                        self.assertEqual(data.get("items", []), [])
                self.assertEqual(snapshot(first["event"]), before)

                # Phase 2: Core process is restarted with the actor token
                # removed from server-held ACL; Temporal is also restarted
                # from its persisted SQLite history.
                gateway.shutdown()
                gateway.server_close()
                gateway_thread.join(timeout=5)
                gateway = gateway_thread = None
                upstream.close()
                upstream = None
                stop_core(core)
                core = None
                core, port = start_core(revoked)
                await wait_core(core, port)
                async with await WorkflowEnvironment.start_local(
                    port=free_port(),
                    dev_server_database_filename=sqlite) as restarted:
                    handle = restarted.client.get_workflow_handle(queue)
                    async with Worker(restarted.client, task_queue=queue,
                                      workflows=[SyntheticRejectSink]):
                        self.assertEqual(
                            await handle.query(SyntheticRejectSink.count), 0)
                        # Two separate OS Worker processes, each polling the
                        # persisted Temporal queue and issuing its own bounded
                        # revoked-actor retry batch against canonical Core TCP.
                        worker_script = r"""
import asyncio, json, os
from pathlib import Path
import httpx
from temporalio.client import Client
from temporalio.worker import Worker
from test_worker_hitl_reject_notification import SyntheticRejectSink

async def run():
    cfg = json.loads(os.environ["AIOPS_CI_REVOKED_WORKER_INPUT"])
    client = await Client.connect(cfg["temporal"])
    async with Worker(client, task_queue=cfg["queue"],
                      workflows=[SyntheticRejectSink]):
        Path(cfg["ready"]).write_text("ready")
        while not Path(cfg["go"]).exists():
            await asyncio.sleep(0.05)
        async with httpx.AsyncClient(base_url=cfg["core"], timeout=20,
                                     trust_env=False) as http:
            async def denied(path, body):
                r = await http.post(path, json=body, headers={
                    "Authorization": "Bearer " + cfg["bearer"]})
                data = r.json()
                assert r.status_code == 401 and data["status"] == "UNKNOWN"
                assert data["execution_allowed"] is False
                assert data["effect_allowed"] is False
                assert data.get("items", []) == []
                assert "receipt_sha256" not in data
            n = cfg["n"]
            await asyncio.gather(
                *[denied(cfg["dead"], cfg["ack"]) for _ in range(n)],
                *[denied(cfg["late_ack"], cfg["ack"]) for _ in range(n)],
                *[denied(cfg["claim"], cfg["claim_body"]) for _ in range(n)])
        Path(cfg["result"]).write_text(json.dumps({
            "pid": os.getpid(), "dead": n, "ack": n, "claim": n}))
        await asyncio.Event().wait()

asyncio.run(run())
"""
                        worker_processes = []
                        ready_paths, result_paths = [], []
                        go_path = Path(self.temp.name) / ("worker-go-" + queue)
                        try:
                            for i in range(2):
                                ready = Path(self.temp.name) / (
                                    f"revoked-worker-{queue}-{i}.ready")
                                result = Path(self.temp.name) / (
                                    f"revoked-worker-{queue}-{i}.json")
                                cfg = {
                                    "temporal": restarted.client.service_client.config.target_host,
                                    "queue": queue, "ready": str(ready),
                                    "go": str(go_path), "result": str(result),
                                    "core": f"http://127.0.0.1:{port}",
                                    "bearer": self.bearer,
                                    "dead": path + "/dead",
                                    "late_ack": path + "/ack",
                                    "claim": claim_path, "ack": ack_body(lease),
                                    "claim_body": {"owner": base.OWNER, "limit": 1},
                                    "n": n,
                                }
                                proc = subprocess.Popen(
                                    [sys.executable, "-c", worker_script],
                                    cwd=str(base.ROOT),
                                    env=dict(os.environ, PYTHONPATH="app:tests",
                                             AIOPS_CI_REVOKED_WORKER_INPUT=json.dumps(cfg)),
                                    stdin=subprocess.DEVNULL,
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
                                worker_processes.append(proc)
                                ready_paths.append(ready)
                                result_paths.append(result)
                            for _ in range(200):
                                self.assertTrue(all(p.poll() is None for p in worker_processes),
                                                "disposable Worker exited early")
                                if all(p.exists() for p in ready_paths):
                                    break
                                await asyncio.sleep(0.05)
                            else:
                                self.fail("two disposable Worker processes not ready")
                            go_path.write_text("go")
                            for _ in range(400):
                                self.assertTrue(all(p.poll() is None for p in worker_processes),
                                                "revoked Worker retry failed")
                                if all(p.exists() for p in result_paths):
                                    break
                                await asyncio.sleep(0.05)
                            else:
                                self.fail("two disposable Worker retries timed out")
                            results = [json.loads(p.read_text()) for p in result_paths]
                            self.assertEqual(len({r["pid"] for r in results}), 2)
                            self.assertTrue(all(
                                r["dead"] == r["ack"] == r["claim"] == n
                                for r in results))
                            self.assertEqual(
                                await handle.query(SyntheticRejectSink.count), 0)
                        finally:
                            for proc in worker_processes:
                                stop_core(proc)
                        async with httpx.AsyncClient(
                            base_url=f"http://127.0.0.1:{port}",
                            timeout=20.0, trust_env=False,
                            limits=httpx.Limits(max_connections=24)) as client:
                            calls = (
                                [call(client, path + "/dead", ack_body(lease),
                                      self.bearer) for _ in range(n)] +
                                [call(client, path + "/ack", ack_body(lease),
                                      self.bearer) for _ in range(n)] +
                                [call(client, claim_path,
                                      {"owner": base.OWNER, "limit": 1},
                                      self.bearer) for _ in range(n)]
                            )
                            denied_acl = await asyncio.gather(*calls)
                            self.assertTrue(all(
                                code == 401 and data["status"] == "UNKNOWN"
                                for code, data in denied_acl))
                            code, data = await call(
                                client, path + "/dead", ack_body(lease),
                                delivery_only)
                            self.assertEqual((code, data["status"]),
                                             (403, "UNKNOWN"))
                            code, data = await call(
                                client, path + "/dead", ack_body(lease),
                                foreign_scoped)
                            self.assertEqual((code, data["status"]),
                                             (403, "UNKNOWN"))
                        self.assertEqual(
                            await handle.query(SyntheticRejectSink.count), 0)

                after = snapshot(first["event"])
                self.assertEqual(before, after)
                with self.psycopg.connect(self.url) as db:
                    self.assertEqual(db.execute(
                        "select count(*) from aiops.hitl_reject_terminal_receipts "
                        "where event_id=%s", (first["event"],)).fetchone()[0], 1)
                    self.assertEqual(db.execute(
                        "select status,attempts from aiops.hitl_decision_outbox "
                        "where event_id=%s", (second["event"],)).fetchone(),
                        ("PENDING", 0))
                    self.assertEqual(db.execute(
                        "select count(*) from aiops.hitl_reject_terminal_receipts "
                        "where event_id=%s", (second["event"],)).fetchone()[0], 0)
                self._no_effect()
                receipt = {
                    "schema": "aiops.worker-postdead-revocation-fencing.v1",
                    "source_head": head,
                    "environment": "CI_DISPOSABLE_SYNTHETIC_ONLY",
                    "core_http": "CANONICAL_CORE_MAIN_TCP_OBSERVED",
                    "migration_014": "CORE_OWNED_RUNTIME_OBSERVED",
                    "dead_event_sha256": hashlib.sha256(
                        first["event"].encode()).hexdigest(),
                    "pending_event_sha256": hashlib.sha256(
                        second["event"].encode()).hexdigest(),
                    "dead_status": "DEAD", "dead_attempts": 8,
                    "pending_status": "PENDING", "pending_attempts": 0,
                    "audit_rows_before": 1, "audit_rows_after": 1,
                    "receipt_sha256_before": before,
                    "receipt_sha256_after": after,
                    "tenant_run_provenance_revoked": True,
                    "provenance_revocation_method": "CI_SIGNED_PROOF_MANIFEST_WITHDRAWAL",
                    "provenance_sql_mutation": False,
                    "provenance_denied_dead": n,
                    "provenance_denied_ack": n,
                    "provenance_denied_claim": n,
                    "actor_acl_revoked_on_core_restart": True,
                    "actor_denied_dead": n,
                    "actor_denied_ack": n,
                    "actor_denied_claim": n,
                    "disposable_worker_processes": 2,
                    "distinct_worker_processes": True,
                    "revoked_worker_retry_requests": n * 2 * 3,
                    "delivery_only_terminal_denied": True,
                    "foreign_tenant_terminal_denied": True,
                    "temporal_persisted_restarts": 1,
                    "core_tcp_restarts": 1,
                    "gateway_close": "INJECTED_AFTER_CORE_TCP_DEAD_COMMIT",
                    "physical_packet_loss": "NOT_TESTED",
                    "temporal_signal_count": 0, "approve_count": 0,
                    "delivered_count": 0, "effect_receipt_count": 0,
                    "execution_allowed": False, "effect_allowed": False,
                    "sql_dead_injection": False,
                    "oidc_glpi_identity": "NOT_ATTESTED",
                    "host_7777": "NOT_VERIFIED_BY_CI",
                    "host_7777_local_operator": "REPORTED_VERIFIED",
                    "universal_exactly_once": "NOT_CLAIMED",
                }
                canonical = json.dumps(
                    receipt, sort_keys=True, separators=(",", ":")).encode()
                receipt["payload_sha256"] = hashlib.sha256(canonical).hexdigest()
                target = Path(os.environ["AIOPS_CI_CANONICAL_DEAD_RECEIPT_DIR"])
                if not str(target).startswith("/tmp/hitl-core-dead-canonical-"):
                    raise RuntimeError("non_disposable_receipt_path")
                target.mkdir(parents=True, exist_ok=True)
                (target / "canonical-dead-revocation.json").write_text(
                    json.dumps(receipt, sort_keys=True, indent=2) + "\n")
            finally:
                if gateway is not None:
                    gateway.shutdown()
                    gateway.server_close()
                if gateway_thread is not None:
                    gateway_thread.join(timeout=5)
                if upstream is not None:
                    upstream.close()
                stop_core(core)


if __name__ == "__main__":
    unittest.main()
