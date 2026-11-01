"""Disposable combined Core HTTP (ASGI) -> Worker -> Temporal REJECT test.

Uses installed PostgreSQL 16 migrations and a *CI-signed synthetic* Run ownership
fixture. No independent GLPI/OIDC source attestation, no human APPROVE, no LIVE,
no poller or executor. HTTP is FastAPI TestClient (in-process), not a network
partition test. Temporal *test Worker* restarts; server does not restart.
"""
import asyncio
import concurrent.futures
import hashlib
import hmac
import json
import socket
import os
import secrets
import subprocess
import sys
import time
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit, urlunsplit

from fastapi import FastAPI
from fastapi.testclient import TestClient
from core import hitl_reject_delivery as delivery
from core import itsm_xref as xref
from worker.hitl_reject_core_wire import deliver_core_reject_once
from test_worker_hitl_reject_notification import SyntheticRejectSink

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ("001_schema.sql", "004_operational_model.sql",
              "009_ai_decision_ledger.sql", "010_evidence_identity.sql",
              "011_hitl_decision_outbox.sql", "012_itsm_xref_read.sql")
PINNED = {
    "009_ai_decision_ledger.sql": "bfed91982654b6baf0026408fa5134a22af421bb",
    "010_evidence_identity.sql": "1ddafd94639af60ce38b6df0acafd7f63d6b4af2",
    "011_hitl_decision_outbox.sql": "b096af57cb19b9618e3d7d4d68a8ef3d56890934",
    "012_itsm_xref_read.sql": "9408dcf9d92d5bfbdb75968a5a0b0a55f2985457",
}
TENANT = "TEN-CI-WORKER"
OWNER = "svc-CI-WORKER"


def git_blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


@unittest.skipUnless(os.getenv("GITHUB_ACTIONS") == "true"
                     and os.getenv("AIOPS_CI_COMBINED_DISPOSABLE") == "YES",
                     "requires explicitly disposable GitHub Actions services")

class _LoopbackAckDropGateway(BaseHTTPRequestHandler):
    """Disposable TCP gateway: forward to actual Core ASGI, drop one ACK reply.

    The client experiences a closed TCP connection after Core committed. This
    is NOT a real Core TCP deployment or a random network partition.
    """
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length < 1 or length > 8192:
            self.send_error(400)
            return
        body = json.loads(self.rfile.read(length))
        response = self.server.core_client.post(
            self.path, json=body, headers={
                "Authorization": self.headers.get("Authorization", "")})
        if self.path.endswith("/ack") and self.server.drop_once:
            self.server.drop_once = False
            self.server.dropped_ack = {
                "path": self.path, "body": body,
                "status_code": response.status_code,
                "response": response.json(),
            }
            # The upstream Core handler returned (and committed its DB ACK).
            # Simulate a network-boundary lost response by closing the TCP
            # socket without writing an HTTP status line or response bytes.
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.close_connection = True
            return
        data = response.content
        self.send_response(response.status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class CombinedCoreWorkerPG16(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        from psycopg import sql
        cls.psycopg, cls.sql = psycopg, sql
        parsed = urlsplit(os.environ["DATABASE_URL"])
        if (parsed.scheme != "postgresql" or parsed.hostname != "postgres"
                or parsed.port != 5432 or parsed.path != "/aiops"
                or parsed.username != "aiops" or parsed.query or parsed.fragment):
            raise RuntimeError("refuse_non_disposable_postgres_target")
        cls.admin_url = os.environ["DATABASE_URL"]
        cls.name = "aiops_worker_core_temporal_ci"
        cls.url = urlunsplit((parsed.scheme, parsed.netloc, "/" + cls.name, "", ""))
        for name, expected in PINNED.items():
            raw = (ROOT / "db/migrations" / name).read_bytes()
            if git_blob(raw) != expected:
                raise RuntimeError("installed_migration_blob_mismatch:" + name)
        cls.created = False
        with psycopg.connect(cls.admin_url, autocommit=True) as admin:
            version = int(admin.execute("show server_version_num").fetchone()[0])
            if not 160000 <= version < 170000:
                raise RuntimeError("requires_postgresql_16")
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(cls.name)))
            cls.created = True
        try:
            with psycopg.connect(cls.url) as db:
                for name in MIGRATIONS:
                    db.execute((ROOT / "db/migrations" / name).read_text())
            cls.temp = tempfile.TemporaryDirectory(prefix="hitl-combined-ci-")
            cls.proof_path = str(Path(cls.temp.name) / "signed-synthetic-owner.json")
            cls.owner_key = secrets.token_hex(48)
            cls.bearer = secrets.token_urlsafe(32)
            cls.env = patch.dict(os.environ, {
                "AIOPS_XREF_READ_AUTHZ_JSON": json.dumps([{
                    "token_sha256": hashlib.sha256(cls.bearer.encode()).hexdigest(),
                    "actor_id": OWNER, "tenant_ids": [TENANT],
                    "permissions": ["hitl:reject:deliver"],
                }]),
                "AIOPS_XREF_OWNER_ATTESTATION_KEY": cls.owner_key,
                "AIOPS_XREF_OWNER_PROOFS_PATH": cls.proof_path,
            })
            cls.env.start()
            cls.db_patch = patch.object(xref, "db",
                                        side_effect=lambda: psycopg.connect(cls.url))
            cls.db_patch.start()
            cls.app = FastAPI()
            cls.app.include_router(delivery.router)
            cls.client = TestClient(cls.app)
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "client"):
            cls.client.close()
        if hasattr(cls, "db_patch"):
            cls.db_patch.stop()
        if hasattr(cls, "env"):
            cls.env.stop()
        if hasattr(cls, "temp"):
            cls.temp.cleanup()
        if getattr(cls, "created", False):
            with cls.psycopg.connect(cls.admin_url, autocommit=True) as admin:
                admin.execute(cls.sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                    cls.sql.Identifier(cls.name)))

    def setUp(self):
        with self.psycopg.connect(self.url) as db:
            db.execute("update aiops.hitl_decision_outbox set status='DEAD' "
                       "where status in ('PENDING','LEASED')")

    def _fixture(self, tenant_id=TENANT):
        suffix = uuid.uuid4().hex
        ids = {k: k.upper() + "-" + suffix for k in (
            "run", "inc", "evidence", "analysis", "critique",
            "proposal", "approval", "event")}
        digest = hashlib.sha256(("CI-SYNTHETIC-REJECT:" + suffix).encode()).hexdigest()
        evidence_ids = json.dumps([ids["evidence"]])
        with self.psycopg.connect(self.url) as db:
            db.execute("insert into aiops.incidents "
                       "(incident_id,title,severity,state,opened_at,source,synthetic) "
                       "values(%s,'CI-only REJECT','P4','OPEN',now(),'ci',true)",
                       (ids["inc"],))
            db.execute("insert into aiops.runs "
                       "(run_id,incident_id,mode,scenario_id,status,idempotency_key) "
                       "values(%s,%s,'DEMO','CI-REJECT','CREATED',%s)",
                       (ids["run"], ids["inc"], "ci-run-" + suffix))
            db.execute("insert into aiops.evidence "
                       "(evidence_id,source,claim,confidence,provenance,payload_hash,payload) "
                       "values(%s,'ci-fixture','synthetic only',0.5,"
                       "'{\"synthetic\":true}',%s,'{}')",
                       (ids["evidence"], digest))
            db.execute("insert into aiops.analysis_records "
                       "(analysis_id,run_id,idempotency_key,revision,contract_version,"
                       "provider,model,prompt_version,evidence_ids,evidence_set_hash,"
                       "output,confidence,status) "
                       "values(%s,%s,%s,1,'ci','ci-fixture','none','ci',%s,%s,%s,0.5,'VALID')",
                       (ids["analysis"], ids["run"], "ci-analysis-" + suffix,
                        evidence_ids, digest, json.dumps({"recommended_actions": [{
                            "action_id": "CI-FIXTURE", "risk_tier": "LOW",
                            "target_ci_id": "CI-SYNTHETIC", "advisory_only": True,
                            "requires_human_approval": True}]})))
            db.execute("insert into aiops.critique_records "
                       "(critique_id,idempotency_key,analysis_id,run_id,contract_version,"
                       "provider,model,validated,evidence_ids,output,diagnostic_confidence) "
                       "values(%s,%s,%s,%s,'ci','ci-fixture','none',true,%s,%s,0.5)",
                       (ids["critique"], "ci-critique-" + suffix, ids["analysis"],
                        ids["run"], evidence_ids, json.dumps({
                            "issues": [], "unsafe_actions": []})))
            db.execute("insert into aiops.action_proposals "
                       "(proposal_id,run_id,analysis_id,critique_id,source_action_id,"
                       "proposal_revision,target_ci_id,action_type,risk_tier,evidence_ids,"
                       "preconditions,expected_postconditions,proposal_hash,status,expires_at) "
                       "values(%s,%s,%s,%s,'CI-FIXTURE',1,'CI-SYNTHETIC',"
                       "'COLLECT_DIAGNOSTICS','LOW',%s,'[\"ci precondition\"]',"
                       "'[\"ci postcondition\"]',%s,'PROPOSED',now()+interval '1 hour')",
                       (ids["proposal"], ids["run"], ids["analysis"],
                        ids["critique"], evidence_ids, digest))
            db.execute("insert into aiops.approval_records "
                       "(approval_id,proposal_id,proposal_hash,actor_id,actor_role,"
                       "decision,nonce,expires_at,audit) "
                       "values(%s,%s,%s,'SYNTHETIC_UNVERIFIED','ci_fixture','REJECT',"
                       "%s,now()+interval '1 hour',%s)",
                       (ids["approval"], ids["proposal"], digest, "ci-nonce-" + suffix,
                        json.dumps({"synthetic": True, "identity_attested": False})))
            db.execute("update aiops.action_proposals set status='REJECTED' "
                       "where proposal_id=%s", (ids["proposal"],))
            db.execute("insert into aiops.hitl_decision_outbox "
                       "(event_id,proposal_id,run_id,proposal_hash,proposal_revision,"
                       "decision,source_status,approval_id) "
                       "values(%s,%s,%s,%s,1,'REJECT','REJECTED',%s)",
                       (ids["event"], ids["proposal"], ids["run"], digest,
                        ids["approval"]))
            db.execute("insert into aiops.tenant_resource_ownership "
                       "(resource_kind,resource_id,tenant_id,source_event_id,"
                       "verified,observed_at,known_at) "
                       "values('run',%s,%s,%s,true,"
                       "now()-interval '10 seconds',now()-interval '5 seconds')",
                       (ids["run"], tenant_id, "SRC-" + suffix))
        return ids

    def _write_synthetic_proofs(self):
        with self.psycopg.connect(self.url) as db:
            rows = db.execute(
                "select resource_kind,resource_id,tenant_id,verified,"
                "source_event_id,observed_at,known_at "
                "from aiops.tenant_resource_ownership").fetchall()
        proofs = {row[0] + "|" + row[1]: hmac.new(
            self.owner_key.encode(), xref._owner_proof_payload(*row),
            hashlib.sha256).hexdigest() for row in rows}
        Path(self.proof_path).write_text(json.dumps({
            "schema": "aiops.core-ownership-proof.v1", "proofs": proofs}))

    def _http(self, path, body, *, bearer=None):
        response = self.client.post(
            path, json=body,
            headers={"Authorization": "Bearer " + (bearer or self.bearer)})
        data = response.json()
        self.assertIs(data["execution_allowed"], False)
        self.assertIs(data["effect_allowed"], False)
        return response.status_code, data

    def _claim(self):
        return self._http(
            f"/api/tenants/{TENANT}/hitl/reject-delivery/claim",
            {"owner": OWNER, "limit": 1})

    def _ack(self, event, item):
        return self._http(
            f"/api/tenants/{TENANT}/hitl/reject-delivery/{event}/ack",
            {"owner": OWNER, "run_id": item["run_id"],
             "proposal_id": item["proposal_id"],
             "proposal_hash": item["proposal_hash"],
             "proposal_revision": item["proposal_revision"],
             "lease_token": item["lease_token"],
             "execution_allowed": False, "effect_allowed": False})

    def _no_effect(self):
        with self.psycopg.connect(self.url) as db:
            self.assertEqual(db.execute(
                "select count(*) from aiops.effect_receipts").fetchone()[0], 0)
            self.assertEqual(db.execute(
                "select count(*) from aiops.hitl_decision_outbox "
                "where decision='APPROVE'").fetchone()[0], 0)

    async def test_01_unsigned_source_denied_before_lease(self):
        ids = self._fixture()
        code, denial = self._claim()
        self.assertEqual(code, 200)
        self.assertEqual(denial["status"], "UNKNOWN")
        self.assertNotIn("run_id", denial)
        with self.psycopg.connect(self.url) as db:
            self.assertEqual(db.execute(
                "select attempts from aiops.hitl_decision_outbox "
                "where event_id=%s", (ids["event"],)).fetchone()[0], 0)
        self._no_effect()

    async def test_02_core_http_temporal_worker_restart_and_ack_response_loss(self):
        from temporalio.testing import WorkflowEnvironment
        from temporalio.worker import Worker

        first = self._fixture()
        self._write_synthetic_proofs()
        queue = "ci-core-hitl-" + uuid.uuid4().hex
        async with await WorkflowEnvironment.start_local() as env:
            handle = await env.client.start_workflow(
                SyntheticRejectSink.run, id=queue, task_queue=queue)
            lost = {"pending": True, "path": None, "body": None}

            async def post(path, body):
                code, response = self._http(path, body)
                if path.endswith("/ack") and lost["pending"]:
                    lost.update(pending=False, path=path, body=dict(body))
                    # Actual Core transaction committed; only the response
                    # is discarded. NOT a real network interruption.
                    raise ConnectionError("CI-injected ACK response loss after commit")
                return code, response

            async def signal(run_id, payload):
                self.assertEqual(payload["decision"], "REJECT")
                self.assertIs(payload["execution_allowed"], False)
                self.assertIs(payload["effect_allowed"], False)
                self.assertTrue(payload["notification_only"])
                self.assertNotIn("lease_token", payload)
                await handle.signal(SyntheticRejectSink.reject_notification, payload)

            async with Worker(env.client, task_queue=queue,
                              workflows=[SyntheticRejectSink]):
                with self.assertRaises(ConnectionError):
                    await deliver_core_reject_once(
                        tenant_id=TENANT, owner=OWNER, post=post, signal=signal)
                self.assertEqual(await handle.query(SyntheticRejectSink.count), 1)
            # Temporal test Worker stops here; Temporal server stays running.
            self.assertIsNotNone(lost["path"])
            code, replay = self._http(lost["path"], lost["body"])
            self.assertEqual((code, replay["status"], replay["idempotent"]),
                             (200, "DELIVERED", True))
            with self.psycopg.connect(self.url) as db:
                self.assertEqual(db.execute(
                    "select attempts,status from aiops.hitl_decision_outbox "
                    "where event_id=%s", (first["event"],)).fetchone(),
                    (1, "DELIVERED"))
            second = self._fixture()
            self._write_synthetic_proofs()
            async with Worker(env.client, task_queue=queue,
                              workflows=[SyntheticRejectSink]):
                receipts = await deliver_core_reject_once(
                    tenant_id=TENANT, owner=OWNER, post=post, signal=signal)
                self.assertEqual(len(receipts), 1)
                self.assertEqual(receipts[0]["status"], "DELIVERED")
                self.assertIs(receipts[0]["effect_allowed"], False)
                signals = await handle.result()
                self.assertEqual(len(signals), 2)
                self.assertEqual({v["run_id"] for v in signals},
                                 {first["run"], second["run"]})
        self.assertEqual(self._claim()[1]["items"], [])
        self._no_effect()

    async def test_03_concurrent_claim_expiry_and_fencing(self):
        ids = self._fixture()
        self._write_synthetic_proofs()
        barrier = threading.Barrier(2)

        def contender():
            barrier.wait(timeout=10)
            return self._claim()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(contender) for _ in range(2)]
            outcomes = [f.result(timeout=20) for f in futures]
        winners = [result[1]["items"][0] for result in outcomes
                   if result[0] == 200 and result[1]["status"] == "LEASED"]
        self.assertEqual(len(winners), 1, outcomes)
        old = winners[0]
        with self.psycopg.connect(self.url) as db:
            db.execute("update aiops.hitl_decision_outbox "
                       "set lease_until=now()-interval '1 second' where event_id=%s",
                       (ids["event"],))
        self.assertEqual(self._ack(ids["event"], old)[1]["status"], "UNKNOWN")
        code, reclaimed = self._claim()
        self.assertEqual((code, reclaimed["status"]), (200, "LEASED"))
        fresh = reclaimed["items"][0]
        self.assertNotEqual(old["lease_token"], fresh["lease_token"])
        self.assertEqual(self._ack(ids["event"], old)[1]["status"], "UNKNOWN")
        self.assertEqual(self._ack(ids["event"], fresh)[1]["status"], "DELIVERED")
        self.assertTrue(self._ack(ids["event"], fresh)[1]["idempotent"])
        with self.psycopg.connect(self.url) as db:
            self.assertEqual(db.execute(
                "select attempts from aiops.hitl_decision_outbox "
                "where event_id=%s", (ids["event"],)).fetchone()[0], 2)
        self._no_effect()

    async def test_04_tcp_gateway_drops_committed_ack_and_worker_restart_no_duplicate(self):
        """Actual loopback TCP response close; Core remains in-process ASGI.

        This qualifies deterministic gateway-side loss, not physical packet
        loss, an independently deployed Core server, or Temporal server restart.
        """
        import httpx
        from temporalio.testing import WorkflowEnvironment
        from temporalio.worker import Worker

        first = self._fixture()
        self._write_synthetic_proofs()
        gateway = ThreadingHTTPServer(("127.0.0.1", 0), _LoopbackAckDropGateway)
        gateway.core_client = self.client
        gateway.drop_once = True
        gateway.dropped_ack = None
        thread = threading.Thread(target=gateway.serve_forever, daemon=True)
        thread.start()
        try:
            trace = []  # Redacted route/status only; never log lease or bearer.
            async with httpx.AsyncClient(
                    base_url=f"http://127.0.0.1:{gateway.server_port}",
                    timeout=10.0, trust_env=False) as tcp:
                async def post(path, body):
                    response = await tcp.post(
                        path, json=body,
                        headers={"Authorization": "Bearer " + self.bearer})
                    payload = response.json()
                    trace.append((path.rsplit("/", 1)[-1], response.status_code,
                                  payload.get("status"), len(payload.get("items", []))))
                    self.assertIs(payload["execution_allowed"], False)
                    self.assertIs(payload["effect_allowed"], False)
                    return response.status_code, payload

                async with await WorkflowEnvironment.start_local() as env:
                    queue = "ci-core-tcp-loss-" + uuid.uuid4().hex
                    handle = await env.client.start_workflow(
                        SyntheticRejectSink.run, id=queue, task_queue=queue)

                    async def signal(run_id, payload):
                        self.assertEqual(payload["decision"], "REJECT")
                        self.assertEqual(payload["run_id"], run_id)
                        self.assertIs(payload["notification_only"], True)
                        self.assertIs(payload["execution_allowed"], False)
                        self.assertIs(payload["effect_allowed"], False)
                        self.assertNotIn("lease_token", payload)
                        await handle.signal(
                            SyntheticRejectSink.reject_notification, payload)

                    async with Worker(env.client, task_queue=queue,
                                      workflows=[SyntheticRejectSink]):
                        with self.assertRaises(httpx.TransportError):
                            await deliver_core_reject_once(
                                tenant_id=TENANT, owner=OWNER,
                                post=post, signal=signal)
                        for _ in range(50):
                            if await handle.query(SyntheticRejectSink.count) == 1:
                                break
                            await asyncio.sleep(0.1)
                        else:
                            self.fail("first REJECT not observed before restart")

                    dropped = gateway.dropped_ack
                    self.assertIsNotNone(dropped)
                    self.assertEqual(dropped["status_code"], 200)
                    self.assertEqual(dropped["response"]["status"], "DELIVERED")
                    self.assertIs(dropped["response"]["idempotent"], False)
                    with self.psycopg.connect(self.url) as db:
                        self.assertEqual(db.execute(
                            "select status,attempts from aiops.hitl_decision_outbox "
                            "where event_id=%s", (first["event"],)).fetchone(),
                            ("DELIVERED", 1))
                    # A fresh TCP request replays EXACTLY the committed ACK.
                    # It cannot send a second Temporal signal or re-claim it.
                    code, receipt = await post(dropped["path"], dropped["body"])
                    self.assertEqual((code, receipt["status"], receipt["idempotent"]),
                                     (200, "DELIVERED", True))
                    code, again = await post(dropped["path"], dropped["body"])
                    self.assertEqual((code, again["idempotent"]), (200, True))
                    code, empty = await post(
                        f"/api/tenants/{TENANT}/hitl/reject-delivery/claim",
                        {"owner": OWNER, "limit": 1})
                    self.assertEqual((code, empty["status"], empty["items"]),
                                     (200, "UNKNOWN", []))
                    # No query while the test Worker is down: Temporal cannot
                    # serve workflow queries without a poller. Final two unique
                    # notifications and one DB attempt prove no duplicate.

                    second = self._fixture()
                    self._write_synthetic_proofs()
                    # Temporal *test Worker* is restarted; server stays alive.
                    async with Worker(env.client, task_queue=queue,
                                      workflows=[SyntheticRejectSink]):
                        receipts = await deliver_core_reject_once(
                            tenant_id=TENANT, owner=OWNER,
                            post=post, signal=signal)
                        self.assertEqual(len(receipts), 1, repr(trace[-3:]))
                        self.assertEqual(receipts[0]["status"], "DELIVERED")
                        signals = await asyncio.wait_for(handle.result(), timeout=20)
                        self.assertEqual(len(signals), 2)
                        self.assertEqual(
                            [item["run_id"] for item in signals],
                            [first["run"], second["run"]])
                        self.assertEqual(
                            len({item["event_id"] for item in signals}), 2)
                    with self.psycopg.connect(self.url) as db:
                        self.assertEqual(db.execute(
                            "select status,attempts from aiops.hitl_decision_outbox "
                            "where event_id=%s", (first["event"],)).fetchone(),
                            ("DELIVERED", 1))
                    self.assertIs(gateway.drop_once, False)
                    self._no_effect()
        finally:
            gateway.shutdown()
            gateway.server_close()
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive(), "TCP gateway did not stop")



    async def test_05_independent_core_tcp_temporal_server_restart_persistent_reject(self):
        """T1 disposable: separate Core TCP PID and persistent Temporal server restart.

        The ACK reply is dropped by a deterministic loopback gateway after the
        independent Core HTTP process commits to PG16. This is NOT packet loss
        on the wire or an external identity attestation.
        """
        import httpx
        from temporalio.testing import WorkflowEnvironment
        from temporalio.worker import Worker

        first = self._fixture()
        self._write_synthetic_proofs()
        # Pick a local-only ephemeral port. Core is a separate OS process;
        # unlike TestClient, requests cross a real TCP Core HTTP boundary.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        code = (
            "from fastapi import FastAPI\n"
            "from core.hitl_reject_delivery import router\n"
            "import uvicorn\n"
            "app = FastAPI()\n"
            "app.include_router(router)\n"
            f"uvicorn.run(app, host='127.0.0.1', port={port}, "
            "access_log=False, log_level='error')\n"
        )
        env_vars = dict(os.environ)
        env_vars["DATABASE_URL"] = self.url
        core_process = subprocess.Popen(
            [sys.executable, "-c", code], cwd=str(ROOT), env=env_vars,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        gateway = None
        gateway_thread = None
        upstream = None
        try:
            for _ in range(100):
                if core_process.poll() is not None:
                    self.fail("independent Core TCP service exited before ready")
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                        break
                except OSError:
                    await asyncio.sleep(0.1)
            else:
                self.fail("independent Core TCP service did not start")

            upstream = httpx.Client(
                base_url=f"http://127.0.0.1:{port}",
                timeout=10.0, trust_env=False,
            )
            gateway = ThreadingHTTPServer(("127.0.0.1", 0), _LoopbackAckDropGateway)
            gateway.core_client = upstream
            gateway.drop_once = True
            gateway.dropped_ack = None
            gateway_thread = threading.Thread(
                target=gateway.serve_forever, daemon=True)
            gateway_thread.start()
            queue = "ci-core-tcp-restart-" + uuid.uuid4().hex
            sqlite_path = str(Path(self.temp.name) / ("temporal-" + queue + ".sqlite"))
            signals_seen = []

            async with httpx.AsyncClient(
                    base_url=f"http://127.0.0.1:{gateway.server_port}",
                    timeout=10.0, trust_env=False) as tcp:
                async def post(path, body):
                    response = await tcp.post(
                        path, json=body,
                        headers={"Authorization": "Bearer " + self.bearer})
                    data = response.json()
                    self.assertIs(data["execution_allowed"], False)
                    self.assertIs(data["effect_allowed"], False)
                    return response.status_code, data

                handle = None

                async def signal(run_id, payload):
                    self.assertEqual(payload["decision"], "REJECT")
                    self.assertEqual(payload["run_id"], run_id)
                    self.assertIs(payload["notification_only"], True)
                    self.assertIs(payload["execution_allowed"], False)
                    self.assertIs(payload["effect_allowed"], False)
                    self.assertNotIn("lease_token", payload)
                    signals_seen.append(payload["event_id"])
                    await handle.signal(
                        SyntheticRejectSink.reject_notification, payload)

                # First real Temporal dev server, with durable disposable SQLite.
                async with await WorkflowEnvironment.start_local(
                        dev_server_database_filename=sqlite_path) as temporal_first:
                    handle = await temporal_first.client.start_workflow(
                        SyntheticRejectSink.run, id=queue, task_queue=queue)
                    async with Worker(
                            temporal_first.client, task_queue=queue,
                            workflows=[SyntheticRejectSink]):
                        with self.assertRaises(httpx.TransportError):
                            await deliver_core_reject_once(
                                tenant_id=TENANT, owner=OWNER,
                                post=post, signal=signal)
                        for _ in range(60):
                            if await handle.query(SyntheticRejectSink.count) == 1:
                                break
                            await asyncio.sleep(0.1)
                        else:
                            self.fail("first durable Temporal REJECT not observed")
                    self.assertEqual(len(signals_seen), 1)
                    with self.psycopg.connect(self.url) as db:
                        self.assertEqual(db.execute(
                            "select status,attempts from aiops.hitl_decision_outbox "
                            "where event_id=%s", (first["event"],)).fetchone(),
                            ("DELIVERED", 1))
                    self.assertEqual(gateway.dropped_ack["response"]["status"],
                                     "DELIVERED")
                # The Temporal SERVER has now shut down, not merely its Worker.
                # Its SQLite file is reused by a newly launched server.
                self.assertTrue(Path(sqlite_path).is_file())
                second = self._fixture()
                self._write_synthetic_proofs()
                async with await WorkflowEnvironment.start_local(
                        dev_server_database_filename=sqlite_path) as temporal_second:
                    handle = temporal_second.client.get_workflow_handle(queue)
                    async with Worker(
                            temporal_second.client, task_queue=queue,
                            workflows=[SyntheticRejectSink]):
                        # Exact committed ACK replay: idempotent, no new signal.
                        dropped = gateway.dropped_ack
                        code, replay = await post(dropped["path"], dropped["body"])
                        self.assertEqual((code, replay["status"], replay["idempotent"]),
                                         (200, "DELIVERED", True))
                        stale = dict(dropped["body"])
                        stale["lease_token"] = "Z" * 48
                        code, denied = await post(dropped["path"], stale)
                        self.assertEqual((code, denied["status"]), (200, "UNKNOWN"))
                        self.assertEqual(len(signals_seen), 1)
                        receipts = await deliver_core_reject_once(
                            tenant_id=TENANT, owner=OWNER, post=post, signal=signal)
                        self.assertEqual(len(receipts), 1)
                        self.assertEqual(receipts[0]["status"], "DELIVERED")
                        result = await asyncio.wait_for(handle.result(), timeout=30)
                        self.assertEqual(
                            [v["run_id"] for v in result],
                            [first["run"], second["run"]])
                        self.assertEqual(
                            len({v["event_id"] for v in result}), 2)
                        self.assertEqual(
                            signals_seen, [first["event"], second["event"]])
                with self.psycopg.connect(self.url) as db:
                    self.assertEqual(db.execute(
                        "select status,attempts from aiops.hitl_decision_outbox "
                        "where event_id=%s", (first["event"],)).fetchone(),
                        ("DELIVERED", 1))
                    self.assertEqual(db.execute(
                        "select status,attempts from aiops.hitl_decision_outbox "
                        "where event_id=%s", (second["event"],)).fetchone(),
                        ("DELIVERED", 1))
                self.assertEqual(self._claim()[1]["items"], [])
                self._no_effect()
        finally:
            if gateway is not None:
                gateway.shutdown()
                gateway.server_close()
            if gateway_thread is not None:
                gateway_thread.join(timeout=5)
            if upstream is not None:
                upstream.close()
            core_process.terminate()
            try:
                core_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                core_process.kill()
                core_process.wait(timeout=5)


    async def test_06_two_temporal_workers_race_one_core_lease_and_restart_server(self):
        """Two live test Workers, one Core TCP lease, one durable REJECT signal.

        Core is an independent loopback Uvicorn process backed by installed
        PG16 009-012. A gateway deliberately drops an ACK HTTP response after
        Core commits. Temporal dev SERVER restarts from disposable SQLite.
        This is NOT physical packet loss or independent GLPI/OIDC attestation.
        """
        import httpx
        from temporalio.testing import WorkflowEnvironment
        from temporalio.worker import Worker

        first = self._fixture()
        self._write_synthetic_proofs()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        core_code = (
            "from fastapi import FastAPI\n"
            "from core.hitl_reject_delivery import router\n"
            "import uvicorn\n"
            "app = FastAPI()\n"
            "app.include_router(router)\n"
            f"uvicorn.run(app, host='127.0.0.1', port={port}, "
            "access_log=False, log_level='error')\n"
        )
        env_vars = dict(os.environ)
        env_vars["DATABASE_URL"] = self.url
        core = subprocess.Popen(
            [sys.executable, "-c", core_code], cwd=str(ROOT), env=env_vars,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        upstream = None
        gateway = None
        gateway_thread = None
        try:
            for _ in range(100):
                self.assertIsNone(core.poll(), "independent Core exited")
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                        break
                except OSError:
                    await asyncio.sleep(0.1)
            else:
                self.fail("independent Core TCP did not become ready")
            upstream = httpx.Client(
                base_url=f"http://127.0.0.1:{port}",
                timeout=10.0, trust_env=False)
            gateway = ThreadingHTTPServer(("127.0.0.1", 0), _LoopbackAckDropGateway)
            gateway.core_client = upstream
            gateway.drop_once = True
            gateway.dropped_ack = None
            gateway_thread = threading.Thread(
                target=gateway.serve_forever, daemon=True)
            gateway_thread.start()
            queue = "ci-two-workers-" + uuid.uuid4().hex
            sqlite_path = str(Path(self.temp.name) / (queue + ".sqlite"))
            signalled = []

            async with httpx.AsyncClient(
                    base_url=f"http://127.0.0.1:{gateway.server_port}",
                    timeout=10.0, trust_env=False) as tcp:
                async def post(path, body):
                    response = await tcp.post(
                        path, json=body,
                        headers={"Authorization": "Bearer " + self.bearer})
                    data = response.json()
                    self.assertIs(data["execution_allowed"], False)
                    self.assertIs(data["effect_allowed"], False)
                    return response.status_code, data

                handle = None

                async def signal(run_id, payload):
                    self.assertEqual(payload["decision"], "REJECT")
                    self.assertEqual(payload["run_id"], run_id)
                    self.assertIs(payload["notification_only"], True)
                    self.assertIs(payload["execution_allowed"], False)
                    self.assertIs(payload["effect_allowed"], False)
                    self.assertNotIn("lease_token", payload)
                    await handle.signal(SyntheticRejectSink.reject_notification, payload)
                    signalled.append(payload["event_id"])

                async with await WorkflowEnvironment.start_local(
                        dev_server_database_filename=sqlite_path) as temporal_first:
                    handle = await temporal_first.client.start_workflow(
                        SyntheticRejectSink.run, id=queue, task_queue=queue)
                    # Two independent Temporal test Worker instances compete
                    # on the same task queue; two concurrent HTTP claim calls
                    # compete for the ONE Core-owned SKIP LOCKED lease.
                    async with Worker(
                            temporal_first.client, task_queue=queue,
                            workflows=[SyntheticRejectSink]), Worker(
                            temporal_first.client, task_queue=queue,
                            workflows=[SyntheticRejectSink]):
                        barrier = asyncio.Barrier(2)

                        async def contender():
                            await barrier.wait()
                            return await deliver_core_reject_once(
                                tenant_id=TENANT, owner=OWNER,
                                post=post, signal=signal)

                        outcomes = await asyncio.gather(
                            contender(), contender(), return_exceptions=True)
                        self.assertEqual(
                            sum(isinstance(x, httpx.TransportError)
                                for x in outcomes), 1, repr(outcomes))
                        self.assertEqual(
                            sum(x == [] for x in outcomes
                                if not isinstance(x, BaseException)),
                            1, repr(outcomes))
                        for _ in range(60):
                            if await handle.query(SyntheticRejectSink.count) == 1:
                                break
                            await asyncio.sleep(0.1)
                        else:
                            self.fail("one REJECT not observed by Temporal")
                    self.assertEqual(signalled, [first["event"]])
                    self.assertEqual(gateway.dropped_ack["response"]["status"],
                                     "DELIVERED")
                    with self.psycopg.connect(self.url) as db:
                        self.assertEqual(db.execute(
                            "select status,attempts from aiops.hitl_decision_outbox "
                            "where event_id=%s", (first["event"],)).fetchone(),
                            ("DELIVERED", 1))

                # The SERVER, not just a Worker, is stopped and restarted.
                self.assertTrue(Path(sqlite_path).is_file())
                second = self._fixture()
                self._write_synthetic_proofs()
                async with await WorkflowEnvironment.start_local(
                        dev_server_database_filename=sqlite_path) as temporal_second:
                    handle = temporal_second.client.get_workflow_handle(queue)
                    dropped = gateway.dropped_ack
                    code, replay = await post(dropped["path"], dropped["body"])
                    self.assertEqual(
                        (code, replay["status"], replay["idempotent"]),
                        (200, "DELIVERED", True))
                    # A forged token cannot reuse the committed receipt.
                    wrong = dict(dropped["body"], lease_token="Z" * 48)
                    code, denied = await post(dropped["path"], wrong)
                    self.assertEqual((code, denied["status"]), (200, "UNKNOWN"))
                    self.assertEqual(signalled, [first["event"]])

                    claim_path = f"/api/tenants/{TENANT}/hitl/reject-delivery/claim"
                    code, lease = await post(
                        claim_path, {"owner": OWNER, "limit": 1})
                    self.assertEqual((code, lease["status"]), (200, "LEASED"))
                    old = lease["items"][0]
                    self.assertEqual(old["event_id"], second["event"])
                    old_ack = {
                        "owner": OWNER, "run_id": old["run_id"],
                        "proposal_id": old["proposal_id"],
                        "proposal_hash": old["proposal_hash"],
                        "proposal_revision": old["proposal_revision"],
                        "lease_token": old["lease_token"],
                        "execution_allowed": False, "effect_allowed": False,
                    }
                    with self.psycopg.connect(self.url) as db:
                        db.execute(
                            "update aiops.hitl_decision_outbox "
                            "set lease_until=now()-interval '1 second' "
                            "where event_id=%s", (second["event"],))
                    code, stale = await post(
                        f"/api/tenants/{TENANT}/hitl/reject-delivery/"
                        f"{second['event']}/ack", old_ack)
                    self.assertEqual((code, stale["status"]), (200, "UNKNOWN"))
                    # Reclaim under a NEW lease; only the current lease can ACK.
                    async with Worker(
                            temporal_second.client, task_queue=queue,
                            workflows=[SyntheticRejectSink]):
                        receipts = await deliver_core_reject_once(
                            tenant_id=TENANT, owner=OWNER,
                            post=post, signal=signal)
                        self.assertEqual(len(receipts), 1)
                        self.assertEqual(receipts[0]["status"], "DELIVERED")
                        self.assertIs(receipts[0]["effect_allowed"], False)
                        received = await asyncio.wait_for(
                            handle.result(), timeout=30)
                    self.assertEqual(
                        [x["event_id"] for x in received],
                        [first["event"], second["event"]])
                    self.assertEqual(signalled, [first["event"], second["event"]])
                    code, stale_after = await post(
                        f"/api/tenants/{TENANT}/hitl/reject-delivery/"
                        f"{second['event']}/ack", old_ack)
                    self.assertEqual((code, stale_after["status"]),
                                     (200, "UNKNOWN"))
                    with self.psycopg.connect(self.url) as db:
                        rows = db.execute(
                            "select event_id,status,attempts "
                            "from aiops.hitl_decision_outbox "
                            "where event_id in (%s,%s) order by event_id",
                            (first["event"], second["event"])).fetchall()
                    self.assertEqual(
                        {row[0]: (row[1], row[2]) for row in rows},
                        {first["event"]: ("DELIVERED", 1),
                         second["event"]: ("DELIVERED", 2)})
                    self.assertEqual(gateway.drop_once, False)
                    self._no_effect()
        finally:
            if gateway is not None:
                gateway.shutdown()
                gateway.server_close()
            if gateway_thread is not None:
                gateway_thread.join(timeout=5)
                self.assertFalse(gateway_thread.is_alive())
            if upstream is not None:
                upstream.close()
            core.terminate()
            try:
                core.wait(timeout=10)
            except subprocess.TimeoutExpired:
                core.kill()
                core.wait(timeout=5)



    async def test_07_multiprocess_worker_restart_stale_ack_and_two_durable_rejects(self):
        """Separate OS Worker PIDs, persisted Temporal SERVER, real Core TCP/PG16.

        A gateway closes one ACK response only AFTER Core's durable commit.
        This is injected gateway-close, NOT physical packet loss/partition.
        """
        import httpx
        from temporalio.testing import WorkflowEnvironment

        first = self._fixture()
        self._write_synthetic_proofs()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            core_port = probe.getsockname()[1]
        core_code = (
            "from fastapi import FastAPI\n"
            "from core.hitl_reject_delivery import router\n"
            "import uvicorn\n"
            "app=FastAPI()\n"
            "app.include_router(router)\n"
            f"uvicorn.run(app, host='127.0.0.1', port={core_port}, "
            "access_log=False, log_level='error')\n"
        )
        core_env = dict(os.environ, DATABASE_URL=self.url)
        core = subprocess.Popen(
            [sys.executable, "-c", core_code], cwd=str(ROOT), env=core_env,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        upstream = gateway = gateway_thread = None
        workers = []
        queue = "ci-multiprocess-" + uuid.uuid4().hex
        sqlite_path = str(Path(self.temp.name) / (queue + ".sqlite"))
        worker_code = (
            "import asyncio,sys\n"
            "from pathlib import Path\n"
            "from temporalio.client import Client\n"
            "from temporalio.worker import Worker\n"
            "from test_worker_hitl_reject_notification import SyntheticRejectSink\n"
            "async def main():\n"
            "  client=await Client.connect(sys.argv[1])\n"
            "  async with Worker(client, task_queue=sys.argv[2], "
            "workflows=[SyntheticRejectSink]):\n"
            "    Path(sys.argv[3]).write_text('ready')\n"
            "    await asyncio.Event().wait()\n"
            "asyncio.run(main())\n"
        )

        async def start_worker(target, generation):
            ready = Path(self.temp.name) / (queue + "-" + generation + ".ready")
            proc = subprocess.Popen(
                [sys.executable, "-c", worker_code, target, queue, str(ready)],
                cwd=str(ROOT), env=dict(os.environ),
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
            workers.append(proc)
            for _ in range(100):
                self.assertIsNone(proc.poll(), "Temporal test Worker process exited")
                if ready.is_file():
                    self.assertGreater(proc.pid, 0)
                    return proc
                await asyncio.sleep(0.1)
            self.fail("Temporal test Worker subprocess not ready")

        def stop_worker(proc):
            self.assertIsNone(proc.poll(), "Worker exited before controlled restart")
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            self.assertIsNotNone(proc.poll())

        def available_port():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.bind(("127.0.0.1", 0))
                return probe.getsockname()[1]

        try:
            for _ in range(100):
                self.assertIsNone(core.poll(), "independent Core TCP exited")
                try:
                    with socket.create_connection(
                            ("127.0.0.1", core_port), timeout=0.1):
                        break
                except OSError:
                    await asyncio.sleep(0.1)
            else:
                self.fail("independent Core TCP not ready")
            upstream = httpx.Client(
                base_url=f"http://127.0.0.1:{core_port}",
                timeout=10.0, trust_env=False)
            gateway = ThreadingHTTPServer(
                ("127.0.0.1", 0), _LoopbackAckDropGateway)
            gateway.core_client = upstream
            gateway.drop_once = True
            gateway.dropped_ack = None
            gateway_thread = threading.Thread(
                target=gateway.serve_forever, daemon=True)
            gateway_thread.start()
            signal_ids = []
            second_ack = None

            async with httpx.AsyncClient(
                    base_url=f"http://127.0.0.1:{gateway.server_port}",
                    timeout=10.0, trust_env=False) as tcp:
                async def post(path, body):
                    nonlocal second_ack
                    response = await tcp.post(
                        path, json=body, headers={
                            "Authorization": "Bearer " + self.bearer})
                    data = response.json()
                    self.assertIs(data["execution_allowed"], False)
                    self.assertIs(data["effect_allowed"], False)
                    if (path.endswith("/ack") and data.get("status") == "DELIVERED"
                            and not data.get("idempotent")):
                        second_ack = (path, dict(body))
                    return response.status_code, data

                handle = None

                async def signal(run_id, payload):
                    self.assertEqual(payload["decision"], "REJECT")
                    self.assertEqual(payload["run_id"], run_id)
                    self.assertIs(payload["notification_only"], True)
                    self.assertIs(payload["execution_allowed"], False)
                    self.assertIs(payload["effect_allowed"], False)
                    self.assertNotIn("lease_token", payload)
                    await handle.signal(
                        SyntheticRejectSink.reject_notification, payload)
                    signal_ids.append(payload["event_id"])

                # Temporal server has a disposable persistent SQLite store.
                temporal_port_one = available_port()
                async with await WorkflowEnvironment.start_local(
                        port=temporal_port_one,
                        dev_server_database_filename=sqlite_path) as server_one:
                    target = f"127.0.0.1:{temporal_port_one}"
                    handle = await server_one.client.start_workflow(
                        SyntheticRejectSink.run, id=queue, task_queue=queue)
                    worker_one = await start_worker(target, "one")
                    with self.assertRaises(httpx.TransportError):
                        await deliver_core_reject_once(
                            tenant_id=TENANT, owner=OWNER, post=post,
                            signal=signal)
                    for _ in range(80):
                        if await handle.query(SyntheticRejectSink.count) == 1:
                            break
                        await asyncio.sleep(0.1)
                    else:
                        self.fail("first REJECT not observed by OS Worker PID")
                    self.assertEqual(signal_ids, [first["event"]])
                    self.assertEqual(
                        gateway.dropped_ack["response"]["status"], "DELIVERED")
                    code, replay = await post(
                        gateway.dropped_ack["path"],
                        gateway.dropped_ack["body"])
                    self.assertEqual(
                        (code, replay["status"], replay["idempotent"]),
                        (200, "DELIVERED", True))
                    with self.psycopg.connect(self.url) as db:
                        self.assertEqual(db.execute(
                            "select status,attempts from aiops.hitl_decision_outbox "
                            "where event_id=%s", (first["event"],)).fetchone(),
                            ("DELIVERED", 1))

                    second = self._fixture()
                    self._write_synthetic_proofs()
                    claim_path = (
                        f"/api/tenants/{TENANT}/hitl/reject-delivery/claim")
                    code, claim = await post(
                        claim_path, {"owner": OWNER, "limit": 1})
                    self.assertEqual((code, claim["status"]), (200, "LEASED"))
                    old = claim["items"][0]
                    self.assertEqual(old["event_id"], second["event"])
                    stale_ack = {
                        "owner": OWNER, "run_id": old["run_id"],
                        "proposal_id": old["proposal_id"],
                        "proposal_hash": old["proposal_hash"],
                        "proposal_revision": old["proposal_revision"],
                        "lease_token": old["lease_token"],
                        "execution_allowed": False, "effect_allowed": False,
                    }
                    with self.psycopg.connect(self.url) as db:
                        db.execute(
                            "update aiops.hitl_decision_outbox "
                            "set lease_until=now()-interval '1 second' "
                            "where event_id=%s", (second["event"],))
                    stop_worker(worker_one)
                    self.assertEqual(signal_ids, [first["event"]])

                # Server and Worker processes are independently restarted.
                self.assertTrue(Path(sqlite_path).is_file())
                temporal_port_two = available_port()
                async with await WorkflowEnvironment.start_local(
                        port=temporal_port_two,
                        dev_server_database_filename=sqlite_path) as server_two:
                    target = f"127.0.0.1:{temporal_port_two}"
                    handle = server_two.client.get_workflow_handle(queue)
                    worker_two = await start_worker(target, "two")
                    self.assertNotEqual(worker_one.pid, worker_two.pid)
                    stale_path = (
                        f"/api/tenants/{TENANT}/hitl/reject-delivery/"
                        f"{second['event']}/ack")
                    code, denied = await post(stale_path, stale_ack)
                    self.assertEqual((code, denied["status"]), (200, "UNKNOWN"))
                    # Invalid binding must never turn a stale lease into ACK.
                    bad = dict(stale_ack, lease_token="Z" * 48)
                    code, denied = await post(stale_path, bad)
                    self.assertEqual((code, denied["status"]), (200, "UNKNOWN"))
                    self.assertEqual(signal_ids, [first["event"]])
                    receipts = await deliver_core_reject_once(
                        tenant_id=TENANT, owner=OWNER, post=post,
                        signal=signal)
                    self.assertEqual(len(receipts), 1)
                    self.assertEqual(receipts[0]["status"], "DELIVERED")
                    self.assertIs(receipts[0]["execution_allowed"], False)
                    self.assertIs(receipts[0]["effect_allowed"], False)
                    self.assertIsNotNone(second_ack)
                    result = await asyncio.wait_for(handle.result(), timeout=30)
                    self.assertEqual(
                        [x["event_id"] for x in result],
                        [first["event"], second["event"]])
                    self.assertEqual(
                        signal_ids, [first["event"], second["event"]])
                    code, replay = await post(*second_ack)
                    self.assertEqual(
                        (code, replay["status"], replay["idempotent"]),
                        (200, "DELIVERED", True))
                    code, denied = await post(stale_path, stale_ack)
                    self.assertEqual((code, denied["status"]), (200, "UNKNOWN"))
                    self.assertEqual(self._claim()[1]["items"], [])
                    with self.psycopg.connect(self.url) as db:
                        rows = db.execute(
                            "select event_id,status,attempts "
                            "from aiops.hitl_decision_outbox "
                            "where event_id in (%s,%s)",
                            (first["event"], second["event"])).fetchall()
                    self.assertEqual(
                        {row[0]: (row[1], row[2]) for row in rows},
                        {first["event"]: ("DELIVERED", 1),
                         second["event"]: ("DELIVERED", 2)})
                    self._no_effect()
                    stop_worker(worker_two)
        finally:
            for proc in workers:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=5)
            if gateway is not None:
                gateway.shutdown()
                gateway.server_close()
            if gateway_thread is not None:
                gateway_thread.join(timeout=5)
            if upstream is not None:
                upstream.close()
            core.terminate()
            try:
                core.wait(timeout=10)
            except subprocess.TimeoutExpired:
                core.kill()
                core.wait(timeout=5)


    async def test_08_cross_tenant_run_fencing_after_two_os_worker_restarts(self):
        """Two tenants, distinct synthetic principals, four OS Worker PIDs.

        Real Core loopback TCP and PostgreSQL 16; Temporal server stop/start
        persists its SQLite history. The first ACK response is deliberately
        closed by the CI gateway after Core commit: NOT physical packet loss.
        Exactly one signal per *tested* REJECT event, not a global guarantee.
        """
        import httpx
        from temporalio.testing import WorkflowEnvironment

        tenant_b = "TEN-CI-WORKER-B"
        owner_b = "svc-CI-WORKER-B"
        bearer_b = secrets.token_urlsafe(32)
        first = self._fixture()
        second = self._fixture(tenant_id=tenant_b)
        self._write_synthetic_proofs()

        # Separate service credentials are each authorized for only one tenant.
        authz = [
            {"token_sha256": hashlib.sha256(token.encode()).hexdigest(),
             "actor_id": actor, "tenant_ids": [tenant],
             "permissions": ["hitl:reject:deliver"]}
            for token, actor, tenant in (
                (self.bearer, OWNER, TENANT),
                (bearer_b, owner_b, tenant_b))
        ]
        auth_patch = patch.dict(os.environ, {
            "AIOPS_XREF_READ_AUTHZ_JSON": json.dumps(authz)})
        auth_patch.start()

        def available_port():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.bind(("127.0.0.1", 0))
                return probe.getsockname()[1]

        core_port = available_port()
        core_code = (
            "from fastapi import FastAPI\n"
            "from core.hitl_reject_delivery import router\n"
            "import uvicorn\n"
            "app=FastAPI()\n"
            "app.include_router(router)\n"
            f"uvicorn.run(app, host='127.0.0.1', port={core_port}, "
            "access_log=False, log_level='error')\n"
        )
        core = subprocess.Popen(
            [sys.executable, "-c", core_code], cwd=str(ROOT),
            env=dict(os.environ, DATABASE_URL=self.url),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        upstream = gateway = gateway_thread = None
        workers = []
        queue = "ci-cross-tenant-" + uuid.uuid4().hex
        sqlite_path = str(Path(self.temp.name) / (queue + ".sqlite"))
        worker_code = (
            "import asyncio,sys\n"
            "from pathlib import Path\n"
            "from temporalio.client import Client\n"
            "from temporalio.worker import Worker\n"
            "from test_worker_hitl_reject_notification import SyntheticRejectSink\n"
            "async def main():\n"
            "  client=await Client.connect(sys.argv[1])\n"
            "  async with Worker(client, task_queue=sys.argv[2], "
            "workflows=[SyntheticRejectSink]):\n"
            "    Path(sys.argv[3]).write_text('ready')\n"
            "    await asyncio.Event().wait()\n"
            "asyncio.run(main())\n"
        )

        async def start_worker(target, generation):
            ready = Path(self.temp.name) / (queue + "-" + generation + ".ready")
            proc = subprocess.Popen(
                [sys.executable, "-c", worker_code, target, queue, str(ready)],
                cwd=str(ROOT), env=dict(os.environ),
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
            workers.append(proc)
            for _ in range(100):
                self.assertIsNone(proc.poll(), "test Worker OS process exited")
                if ready.is_file():
                    return proc
                await asyncio.sleep(0.1)
            self.fail("test Worker OS process not ready")

        def stop_worker(proc):
            self.assertIsNone(proc.poll(), "Worker exited before planned restart")
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            self.assertIsNotNone(proc.poll())

        try:
            for _ in range(100):
                self.assertIsNone(core.poll(), "independent Core TCP exited")
                try:
                    with socket.create_connection(
                            ("127.0.0.1", core_port), timeout=0.1):
                        break
                except OSError:
                    await asyncio.sleep(0.1)
            else:
                self.fail("independent Core TCP not ready")
            upstream = httpx.Client(
                base_url=f"http://127.0.0.1:{core_port}",
                timeout=10.0, trust_env=False)
            gateway = ThreadingHTTPServer(
                ("127.0.0.1", 0), _LoopbackAckDropGateway)
            gateway.core_client = upstream
            gateway.drop_once = True
            gateway.dropped_ack = None
            gateway_thread = threading.Thread(
                target=gateway.serve_forever, daemon=True)
            gateway_thread.start()

            signal_ids = []
            second_ack = None
            run_tenants = {first["run"]: TENANT, second["run"]: tenant_b}
            async with httpx.AsyncClient(
                    base_url=f"http://127.0.0.1:{gateway.server_port}",
                    timeout=10.0, trust_env=False) as tcp:
                async def post_as(token, path, body):
                    nonlocal second_ack
                    response = await tcp.post(
                        path, json=body,
                        headers={"Authorization": "Bearer " + token})
                    data = response.json()
                    self.assertIs(data["execution_allowed"], False)
                    self.assertIs(data["effect_allowed"], False)
                    if (token == bearer_b and path.endswith("/ack")
                            and data.get("status") == "DELIVERED"
                            and data.get("idempotent") is False):
                        second_ack = (path, dict(body))
                    return response.status_code, data

                async def post_a(path, body):
                    return await post_as(self.bearer, path, body)

                async def post_b(path, body):
                    return await post_as(bearer_b, path, body)

                handle = None

                async def signal(run_id, payload):
                    self.assertEqual(payload["decision"], "REJECT")
                    self.assertIs(payload["notification_only"], True)
                    self.assertEqual(payload["tenant_id"], run_tenants[run_id])
                    self.assertEqual(payload["run_id"], run_id)
                    self.assertIs(payload["execution_allowed"], False)
                    self.assertIs(payload["effect_allowed"], False)
                    self.assertNotIn("lease_token", payload)
                    self.assertNotIn(payload["event_id"], signal_ids)
                    await handle.signal(
                        SyntheticRejectSink.reject_notification, payload)
                    signal_ids.append(payload["event_id"])

                temporal_port_one = available_port()
                async with await WorkflowEnvironment.start_local(
                        port=temporal_port_one,
                        dev_server_database_filename=sqlite_path) as server_one:
                    target = f"127.0.0.1:{temporal_port_one}"
                    handle = await server_one.client.start_workflow(
                        SyntheticRejectSink.run, id=queue, task_queue=queue)
                    worker_one = await start_worker(target, "one")
                    with self.assertRaises(httpx.TransportError):
                        await deliver_core_reject_once(
                            tenant_id=TENANT, owner=OWNER, post=post_a,
                            signal=signal)
                    for _ in range(80):
                        if await handle.query(SyntheticRejectSink.count) == 1:
                            break
                        await asyncio.sleep(0.1)
                    else:
                        self.fail("first tenant REJECT not observed")
                    self.assertEqual(signal_ids, [first["event"]])
                    self.assertEqual(
                        gateway.dropped_ack["response"]["status"], "DELIVERED")
                    self.assertIs(
                        gateway.dropped_ack["response"]["effect_allowed"], False)
                    path_a = gateway.dropped_ack["path"]
                    body_a = gateway.dropped_ack["body"]
                    code, replay = await post_a(path_a, body_a)
                    self.assertEqual(
                        (code, replay["status"], replay["idempotent"]),
                        (200, "DELIVERED", True))

                    # First independent OS Worker restart, same Temporal server.
                    stop_worker(worker_one)
                    worker_two = await start_worker(target, "two")
                    self.assertNotEqual(worker_one.pid, worker_two.pid)
                    self.assertEqual(
                        await handle.query(SyntheticRejectSink.count), 1)

                    path_claim_b = (
                        f"/api/tenants/{tenant_b}/hitl/reject-delivery/claim")
                    code, claim = await post_b(
                        path_claim_b, {"owner": owner_b, "limit": 1})
                    self.assertEqual((code, claim["status"]), (200, "LEASED"))
                    self.assertEqual(len(claim["items"]), 1)
                    old = claim["items"][0]
                    self.assertEqual(old["event_id"], second["event"])
                    self.assertEqual(old["tenant_id"], tenant_b)
                    body_b = {
                        "owner": owner_b, "run_id": old["run_id"],
                        "proposal_id": old["proposal_id"],
                        "proposal_hash": old["proposal_hash"],
                        "proposal_revision": old["proposal_revision"],
                        "lease_token": old["lease_token"],
                        "execution_allowed": False, "effect_allowed": False,
                    }
                    path_b = (
                        f"/api/tenants/{tenant_b}/hitl/reject-delivery/"
                        f"{second['event']}/ack")
                    # Cross-tenant actor, Run, proposal and lease substitutions
                    # cannot acknowledge either tenant's durable event.
                    for post, path, body, expected_code in (
                        (post_b, path_a, body_a, 403),
                        (post_a, path_b, body_b, 403),
                        (post_b, path_b, dict(body_b, run_id=first["run"]), 200),
                        (post_b, path_b, dict(
                            body_b, proposal_id=first["proposal"]), 200),
                        (post_b, path_b, dict(
                            body_b, proposal_hash="f" * 64), 200),
                        (post_b, path_b, dict(
                            body_b, proposal_revision=2), 200),
                        (post_b, path_b, dict(
                            body_b, lease_token="Z" * 48), 200),
                    ):
                        code, denied = await post(path, body)
                        self.assertEqual(code, expected_code)
                        self.assertEqual(denied["status"], "UNKNOWN")
                    with self.psycopg.connect(self.url) as db:
                        db.execute(
                            "update aiops.hitl_decision_outbox "
                            "set lease_until=now()-interval '1 second' "
                            "where event_id=%s", (second["event"],))
                    code, denied = await post_b(path_b, body_b)
                    self.assertEqual((code, denied["status"]), (200, "UNKNOWN"))
                    self.assertEqual(signal_ids, [first["event"]])
                    stop_worker(worker_two)

                # Persisted Temporal SERVER stop/start, then a second
                # independent OS Worker restart (three distinct PIDs).
                self.assertTrue(Path(sqlite_path).is_file())
                temporal_port_two = available_port()
                async with await WorkflowEnvironment.start_local(
                        port=temporal_port_two,
                        dev_server_database_filename=sqlite_path) as server_two:
                    target = f"127.0.0.1:{temporal_port_two}"
                    handle = server_two.client.get_workflow_handle(queue)
                    worker_three = await start_worker(target, "three")
                    self.assertEqual(
                        len({worker_one.pid, worker_two.pid, worker_three.pid}),
                        3)
                    code, denied = await post_b(path_b, body_b)
                    self.assertEqual((code, denied["status"]), (200, "UNKNOWN"))
                    receipts = await deliver_core_reject_once(
                        tenant_id=tenant_b, owner=owner_b, post=post_b,
                        signal=signal)
                    self.assertEqual(len(receipts), 1)
                    self.assertEqual(receipts[0]["status"], "DELIVERED")
                    self.assertIs(receipts[0]["execution_allowed"], False)
                    self.assertIs(receipts[0]["effect_allowed"], False)
                    self.assertIsNotNone(second_ack)
                    result = await asyncio.wait_for(handle.result(), timeout=30)
                    self.assertEqual(
                        [x["event_id"] for x in result],
                        [first["event"], second["event"]])
                    self.assertEqual(
                        signal_ids, [first["event"], second["event"]])
                    for post, path, body in (
                        (post_a, path_a, body_a),
                        (post_b, *second_ack)):
                        code, replay = await post(path, body)
                        self.assertEqual(
                            (code, replay["status"], replay["idempotent"]),
                            (200, "DELIVERED", True))
                    code, denied = await post_b(path_b, body_b)
                    self.assertEqual((code, denied["status"]), (200, "UNKNOWN"))
                    for post, tenant, owner in (
                        (post_a, TENANT, OWNER),
                        (post_b, tenant_b, owner_b)):
                        code, empty = await post(
                            f"/api/tenants/{tenant}/hitl/reject-delivery/claim",
                            {"owner": owner, "limit": 1})
                        self.assertEqual((code, empty["items"]), (200, []))
                    with self.psycopg.connect(self.url) as db:
                        rows = db.execute(
                            "select event_id,status,attempts,lease_owner,decision "
                            "from aiops.hitl_decision_outbox "
                            "where event_id in (%s,%s)",
                            (first["event"], second["event"])).fetchall()
                    self.assertEqual(
                        {r[0]: r[1:] for r in rows},
                        {first["event"]: ("DELIVERED", 1, OWNER, "REJECT"),
                         second["event"]: ("DELIVERED", 2, owner_b, "REJECT")})
                    self._no_effect()

                    # Core's eighth and final lease attempt is real HTTP/PG16.
                    # DEAD is deliberately applied by the disposable SQL fault
                    # controller: Core v1 does not expose a DEAD transition API.
                    # This must never be misreported as a runtime dead-letter.
                    dead = self._fixture(tenant_id=tenant_b)
                    self._write_synthetic_proofs()
                    with self.psycopg.connect(self.url) as db:
                        db.execute(
                            "update aiops.hitl_decision_outbox "
                            "set status='LEASED', attempts=7, lease_owner=%s, "
                            "lease_token=%s, lease_until=now()-interval '1 second' "
                            "where event_id=%s",
                            (owner_b, "EXPIRED-CI-LEASE", dead["event"]))
                    code, last = await post_b(
                        path_claim_b, {"owner": owner_b, "limit": 1})
                    self.assertEqual((code, last["status"]), (200, "LEASED"))
                    self.assertEqual(
                        [item["event_id"] for item in last["items"]],
                        [dead["event"]])
                    final_lease = last["items"][0]
                    dead_path = (
                        f"/api/tenants/{tenant_b}/hitl/reject-delivery/"
                        f"{dead['event']}/ack")
                    dead_ack = {
                        "owner": owner_b, "run_id": final_lease["run_id"],
                        "proposal_id": final_lease["proposal_id"],
                        "proposal_hash": final_lease["proposal_hash"],
                        "proposal_revision": final_lease["proposal_revision"],
                        "lease_token": final_lease["lease_token"],
                        "execution_allowed": False, "effect_allowed": False,
                    }
                    # A foreign tenant, forged token and expired eighth lease
                    # cannot acknowledge the third (never-signalled) event.
                    code, denied = await post_a(dead_path, dead_ack)
                    self.assertEqual((code, denied["status"]), (403, "UNKNOWN"))
                    code, denied = await post_b(
                        dead_path, dict(dead_ack, lease_token="FORGED"))
                    self.assertEqual((code, denied["status"]), (200, "UNKNOWN"))
                    with self.psycopg.connect(self.url) as db:
                        db.execute(
                            "update aiops.hitl_decision_outbox "
                            "set lease_until=now()-interval '1 second' "
                            "where event_id=%s", (dead["event"],))
                    code, denied = await post_b(dead_path, dead_ack)
                    self.assertEqual((code, denied["status"]), (200, "UNKNOWN"))
                    code, empty = await post_b(
                        path_claim_b, {"owner": owner_b, "limit": 1})
                    self.assertEqual((code, empty["items"]), (200, []))
                    # Negative Core runtime qualification: exhausting the
                    # eighth lease prevents another claim, but does NOT move
                    # the row to DEAD. SQL fault injection below is separate.
                    with self.psycopg.connect(self.url) as db:
                        before_injection = db.execute(
                            "select status,attempts,lease_until<now(),"
                            "delivered_at,last_error "
                            "from aiops.hitl_decision_outbox where event_id=%s",
                            (dead["event"],)).fetchone()
                    self.assertEqual(
                        before_injection, ("LEASED", 8, True, None, None))
                    with self.psycopg.connect(self.url) as db:
                        terminal = db.execute(
                            "update aiops.hitl_decision_outbox "
                            "set status='DEAD',last_error=%s "
                            "where event_id=%s and attempts=8 "
                            "and lease_until<now() returning status,attempts",
                            ("CI_INJECTED_RETRY_EXHAUSTED", dead["event"])
                        ).fetchone()
                    self.assertEqual(terminal, ("DEAD", 8))
                    self.assertEqual(
                        signal_ids, [first["event"], second["event"]])
                    self._no_effect()
                    stop_worker(worker_three)

                # A SECOND persisted Temporal SERVER stop/start, plus a third
                # independent OS Worker restart. Check both durable delivered
                # receipts and the SQL-injected DEAD event after recovery.
                self.assertTrue(Path(sqlite_path).is_file())
                temporal_port_three = available_port()
                async with await WorkflowEnvironment.start_local(
                        port=temporal_port_three,
                        dev_server_database_filename=sqlite_path) as server_three:
                    target = f"127.0.0.1:{temporal_port_three}"
                    handle = server_three.client.get_workflow_handle(queue)
                    worker_four = await start_worker(target, "four")
                    self.assertEqual(len({
                        worker_one.pid, worker_two.pid,
                        worker_three.pid, worker_four.pid}), 4)
                    history = await asyncio.wait_for(handle.result(), timeout=30)
                    self.assertEqual(
                        [entry["event_id"] for entry in history],
                        [first["event"], second["event"]])
                    for post, path, body in (
                        (post_a, path_a, body_a),
                        (post_b, *second_ack)):
                        code, replay = await post(path, body)
                        self.assertEqual(
                            (code, replay["status"], replay["idempotent"]),
                            (200, "DELIVERED", True))
                    for post, path, body, expected in (
                        (post_b, path_b, body_b, 200),
                        (post_a, dead_path, dead_ack, 403),
                        (post_b, dead_path, dead_ack, 200),
                        (post_b, dead_path,
                         dict(dead_ack, lease_token="FORGED"), 200)):
                        code, denied = await post(path, body)
                        self.assertEqual((code, denied["status"]),
                                         (expected, "UNKNOWN"))
                    for post, tenant, owner in (
                        (post_a, TENANT, OWNER),
                        (post_b, tenant_b, owner_b)):
                        code, empty = await post(
                            f"/api/tenants/{tenant}/hitl/reject-delivery/claim",
                            {"owner": owner, "limit": 1})
                        self.assertEqual((code, empty["items"]), (200, []))
                    with self.psycopg.connect(self.url) as db:
                        rows = db.execute(
                            "select event_id,status,attempts,decision "
                            "from aiops.hitl_decision_outbox "
                            "where event_id in (%s,%s,%s)",
                            (first["event"], second["event"],
                             dead["event"])).fetchall()
                    self.assertEqual(
                        {row[0]: row[1:] for row in rows},
                        {first["event"]: ("DELIVERED", 1, "REJECT"),
                         second["event"]: ("DELIVERED", 2, "REJECT"),
                         dead["event"]: ("DEAD", 8, "REJECT")})
                    self.assertEqual(
                        signal_ids, [first["event"], second["event"]])
                    self._no_effect()
                    stop_worker(worker_four)
        finally:
            for proc in workers:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=5)
            if gateway is not None:
                gateway.shutdown()
                gateway.server_close()
            if gateway_thread is not None:
                gateway_thread.join(timeout=5)
            if upstream is not None:
                upstream.close()
            core.terminate()
            try:
                core.wait(timeout=10)
            except subprocess.TimeoutExpired:
                core.kill()
                core.wait(timeout=5)
            auth_patch.stop()


    async def test_09_no_core_runtime_dead_transition_after_eighth_lease(self):
        """Negative contract: Core claim/ACK exhausts retry without DEAD.

        Only the existing disposable SQL fault controller can mark DEAD.
        No Temporal notification is emitted for this never-delivered event.
        """
        ids = self._fixture()
        self._write_synthetic_proofs()
        with self.psycopg.connect(self.url) as db:
            db.execute(
                "update aiops.hitl_decision_outbox "
                "set status='LEASED',attempts=7,lease_owner=%s,"
                "lease_token=%s,lease_until=now()-interval '1 second' "
                "where event_id=%s",
                (OWNER, secrets.token_urlsafe(32), ids["event"]))
        code, claim = self._claim()
        self.assertEqual((code, claim["status"]), (200, "LEASED"))
        self.assertEqual(len(claim["items"]), 1)
        lease = claim["items"][0]
        self.assertEqual(lease["event_id"], ids["event"])
        self.assertEqual(lease["decision"], "REJECT")
        self.assertIs(lease["execution_allowed"], False)
        self.assertIs(lease["effect_allowed"], False)
        with self.psycopg.connect(self.url) as db:
            db.execute(
                "update aiops.hitl_decision_outbox "
                "set lease_until=now()-interval '1 second' "
                "where event_id=%s", (ids["event"],))
        code, denied = self._ack(ids["event"], lease)
        self.assertEqual((code, denied["status"]), (200, "UNKNOWN"))
        for _ in range(2):
            code, empty = self._claim()
            self.assertEqual((code, empty["items"]), (200, []))
            code, denied = self._ack(ids["event"], lease)
            self.assertEqual((code, denied["status"]), (200, "UNKNOWN"))
        # Wrong tenant and a forged token cannot bypass retry exhaustion.
        ack_path = (
            f"/api/tenants/{TENANT}/hitl/reject-delivery/{ids['event']}/ack")
        ack = {
            "owner": OWNER, "run_id": lease["run_id"],
            "proposal_id": lease["proposal_id"],
            "proposal_hash": lease["proposal_hash"],
            "proposal_revision": lease["proposal_revision"],
            "lease_token": "Z" * 48,
            "execution_allowed": False, "effect_allowed": False,
        }
        code, forged = self._http(ack_path, ack)
        self.assertEqual((code, forged["status"]), (200, "UNKNOWN"))
        code, foreign = self._http(
            f"/api/tenants/FOREIGN-CI/hitl/reject-delivery/"
            f"{ids['event']}/ack", dict(ack, lease_token=lease["lease_token"]))
        self.assertEqual((code, foreign["status"]), (403, "UNKNOWN"))
        with self.psycopg.connect(self.url) as db:
            state = db.execute(
                "select status,attempts,lease_until<now(),"
                "delivered_at,last_error,decision "
                "from aiops.hitl_decision_outbox where event_id=%s",
                (ids["event"],)).fetchone()
        self.assertEqual(
            state, ("LEASED", 8, True, None, None, "REJECT"))
        self._no_effect()


    async def test_10_core_dead_contract_matrix_no_signal_across_temporal_restarts(self):
        """Negative-only future Core DEAD contract: exhausted leases stay LEASED.

        Two synthetic tenants, actual Core claim/ACK and PG16, exact owner/token/
        expiry/Run/proposal fencing. The never-signalled REJECT events remain
        LEASED at attempts=8 across TWO persisted Temporal server restarts.
        This does not implement, inject or attest a runtime DEAD transition.
        """
        from temporalio.testing import WorkflowEnvironment
        from temporalio.worker import Worker

        tenant_b = "TEN-CI-DEAD-MATRIX-B"
        owner_b = "svc-CI-DEAD-MATRIX-B"
        bearer_b = secrets.token_urlsafe(32)
        first = self._fixture()
        second = self._fixture(tenant_id=tenant_b)
        self._write_synthetic_proofs()
        authz = [
            {"token_sha256": hashlib.sha256(token.encode()).hexdigest(),
             "actor_id": actor, "tenant_ids": [tenant],
             "permissions": ["hitl:reject:deliver"]}
            for token, actor, tenant in (
                (self.bearer, OWNER, TENANT),
                (bearer_b, owner_b, tenant_b))
        ]
        auth_patch = patch.dict(os.environ, {
            "AIOPS_XREF_READ_AUTHZ_JSON": json.dumps(authz)})
        auth_patch.start()
        try:
            cases = ((TENANT, OWNER, self.bearer, first),
                     (tenant_b, owner_b, bearer_b, second))
            # The seven earlier attempts are a disposable SQL fault fixture.
            # Attempt eight is acquired ONLY through the actual Core handler.
            with self.psycopg.connect(self.url) as db:
                for tenant, owner, token, ids in cases:
                    db.execute(
                        "update aiops.hitl_decision_outbox "
                        "set status='LEASED',attempts=7,lease_owner=%s,"
                        "lease_token=%s,lease_until=now()-interval '1 second' "
                        "where event_id=%s",
                        (owner, secrets.token_urlsafe(32), ids["event"]))
            leased = []
            for tenant, owner, token, ids in cases:
                claim_path = f"/api/tenants/{tenant}/hitl/reject-delivery/claim"
                code, claim = self._http(
                    claim_path, {"owner": owner, "limit": 1}, bearer=token)
                self.assertEqual((code, claim["status"]), (200, "LEASED"))
                self.assertEqual(len(claim["items"]), 1)
                item = claim["items"][0]
                self.assertEqual(
                    (item["event_id"], item["tenant_id"], item["run_id"],
                     item["proposal_id"], item["proposal_revision"],
                     item["lease_owner"], item["decision"]),
                    (ids["event"], tenant, ids["run"], ids["proposal"],
                     1, owner, "REJECT"))
                self.assertEqual(item["proposal_hash"],
                                 hashlib.sha256(
                                     ("CI-SYNTHETIC-REJECT:" +
                                      ids["run"].split("-")[-1]).encode()
                                 ).hexdigest())
                self.assertTrue(item["lease_token"])
                self.assertTrue(item["lease_until"])
                self.assertIs(item["execution_allowed"], False)
                self.assertIs(item["effect_allowed"], False)
                path = (f"/api/tenants/{tenant}/hitl/reject-delivery/"
                        f"{ids['event']}/ack")
                body = {
                    "owner": owner, "run_id": item["run_id"],
                    "proposal_id": item["proposal_id"],
                    "proposal_hash": item["proposal_hash"],
                    "proposal_revision": item["proposal_revision"],
                    "lease_token": item["lease_token"],
                    "execution_allowed": False, "effect_allowed": False,
                }
                leased.append((tenant, owner, token, ids, item, path, body))

            self.assertNotEqual(first["event"], second["event"])
            self.assertNotEqual(leased[0][4]["lease_token"],
                                leased[1][4]["lease_token"])
            for i, (tenant, owner, token, ids, item, path, body) in enumerate(leased):
                other = leased[1-i]
                # Each mutation is validly shaped: Core must reject by binding,
                # not because the JSON is malformed.
                negatives = (
                    ("owner", dict(body, owner=other[1])),
                    ("run", dict(body, run_id=other[3]["run"])),
                    ("proposal", dict(body, proposal_id=other[3]["proposal"])),
                    ("hash", dict(body, proposal_hash="f" * 64)),
                    ("revision", dict(body, proposal_revision=2)),
                    ("token", dict(body, lease_token="Z" * 48)),
                    ("execution", dict(body, execution_allowed=True)),
                    ("effect", dict(body, effect_allowed=True)),
                )
                for dimension, forged in negatives:
                    with self.subTest(tenant=tenant, dimension=dimension):
                        code, denied = self._http(path, forged, bearer=token)
                        self.assertEqual((code, denied["status"]),
                                         (200, "UNKNOWN"))
                # Actor's tenant scope is independently checked before lookup.
                code, denied = self._http(path, body, bearer=other[2])
                self.assertEqual((code, denied["status"]), (403, "UNKNOWN"))
                foreign_path = path.replace(
                    f"/tenants/{tenant}/", "/tenants/FOREIGN-CI/")
                code, denied = self._http(
                    foreign_path, body, bearer=token)
                self.assertEqual((code, denied["status"]), (403, "UNKNOWN"))

            # Expire both eighth leases: valid old ACKs become stale. Do not
            # inject DEAD or mutate any Core-owned runtime terminal state.
            with self.psycopg.connect(self.url) as db:
                db.execute(
                    "update aiops.hitl_decision_outbox "
                    "set lease_until=now()-interval '1 second' "
                    "where event_id in (%s,%s)",
                    (first["event"], second["event"]))
            for tenant, owner, token, ids, item, path, body in leased:
                for _ in range(2):
                    code, stale = self._http(path, body, bearer=token)
                    self.assertEqual((code, stale["status"]), (200, "UNKNOWN"))

            def assert_exhausted():
                with self.psycopg.connect(self.url) as db:
                    rows = db.execute(
                        "select event_id,status,attempts,lease_owner,"
                        "lease_token,lease_until<now(),delivered_at,"
                        "last_error,decision,proposal_hash,proposal_revision "
                        "from aiops.hitl_decision_outbox "
                        "where event_id in (%s,%s)",
                        (first["event"], second["event"])).fetchall()
                self.assertEqual(len(rows), 2)
                by_id = {row[0]: row[1:] for row in rows}
                for tenant, owner, token, ids, item, path, body in leased:
                    self.assertEqual(
                        by_id[ids["event"]],
                        ("LEASED", 8, owner, item["lease_token"],
                         True, None, None, "REJECT",
                         item["proposal_hash"], item["proposal_revision"]))
                self._no_effect()

            assert_exhausted()
            queue = "ci-dead-negative-" + uuid.uuid4().hex
            sqlite_path = str(Path(self.temp.name) / (queue + ".sqlite"))
            async def no_signal(_run_id, _payload):
                self.fail("exhausted LEASED event must not signal Temporal")

            async def post_as(tenant, owner, token, path, body):
                return self._http(path, body, bearer=token)

            # Three separate disposable Temporal server instances reuse one
            # persisted SQLite store. No Worker-side DEAD mutation or signal.
            for generation in range(3):
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                    probe.bind(("127.0.0.1", 0))
                    port = probe.getsockname()[1]
                async with await WorkflowEnvironment.start_local(
                        port=port,
                        dev_server_database_filename=sqlite_path) as server:
                    if generation == 0:
                        handle = await server.client.start_workflow(
                            SyntheticRejectSink.run, id=queue, task_queue=queue)
                    else:
                        handle = server.client.get_workflow_handle(queue)
                    async with Worker(
                            server.client, task_queue=queue,
                            workflows=[SyntheticRejectSink]):
                        for tenant, owner, token, ids, item, path, body in leased:
                            async def post(route, request, _token=token):
                                return self._http(route, request, bearer=_token)
                            receipts = await deliver_core_reject_once(
                                tenant_id=tenant, owner=owner,
                                post=post, signal=no_signal)
                            self.assertEqual(receipts, [])
                            code, replay = self._http(path, body, bearer=token)
                            self.assertEqual((code, replay["status"]),
                                             (200, "UNKNOWN"))
                        self.assertEqual(
                            await handle.query(SyntheticRejectSink.count), 0)
                        assert_exhausted()
                self.assertTrue(Path(sqlite_path).is_file())
            # This is a negative Core runtime qualification, NOT DEAD success.
            assert_exhausted()
        finally:
            auth_patch.stop()


if __name__ == "__main__":
    unittest.main()
