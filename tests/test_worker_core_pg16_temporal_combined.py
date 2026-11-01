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

    def _fixture(self):
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
                       (ids["run"], TENANT, "SRC-" + suffix))
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
            async with httpx.AsyncClient(
                    base_url=f"http://127.0.0.1:{gateway.server_port}",
                    timeout=10.0, trust_env=False) as tcp:
                async def post(path, body):
                    response = await tcp.post(
                        path, json=body,
                        headers={"Authorization": "Bearer " + self.bearer})
                    payload = response.json()
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
                    # No query while the test Worker is down: Temporal cannot\n                    # serve workflow queries without a poller. Final two unique\n                    # notifications and one DB attempt prove no duplicate.\n\n                    second = self._fixture()
                    self._write_synthetic_proofs()
                    # Temporal *test Worker* is restarted; server stays alive.
                    async with Worker(env.client, task_queue=queue,
                                      workflows=[SyntheticRejectSink]):
                        receipts = await deliver_core_reject_once(
                            tenant_id=TENANT, owner=OWNER,
                            post=post, signal=signal)
                        self.assertEqual(len(receipts), 1)
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



if __name__ == "__main__":
    unittest.main()
