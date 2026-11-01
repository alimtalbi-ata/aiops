"""Real Core REJECT claim/ACK handlers on populated disposable PostgreSQL 16.

No GLPI network, human approval, executor or LIVE effects. This module is
imported by the existing installed-migration Quality test (no workflow edits).
Signed ownership is a CI-only integrity fixture, NOT GLPI actor authority.
"""
import concurrent.futures
import hashlib
import hmac
import json
import os
import secrets
import tempfile
import threading
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit, urlunsplit

from core import hitl_reject_delivery as delivery
from core import itsm_xref as x

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ("001_schema.sql", "004_operational_model.sql",
              "009_ai_decision_ledger.sql", "010_evidence_identity.sql",
              "011_hitl_decision_outbox.sql", "012_itsm_xref_read.sql")


@unittest.skipUnless(
    os.environ.get("GITHUB_ACTIONS") == "true"
    and os.environ.get("AIOPS_XREF_CI_DISPOSABLE") == "1",
    "Only disposable GitHub Actions PostgreSQL 16")
class CoreRejectPopulatedPG16(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        from psycopg import sql
        cls.psycopg, cls.sql = psycopg, sql
        parsed = urlsplit(os.environ["DATABASE_URL"])
        if (parsed.scheme not in ("postgresql", "postgres")
                or parsed.hostname != "127.0.0.1" or parsed.port != 5432
                or parsed.path != "/aiops" or parsed.username != "aiops"
                or parsed.query or parsed.fragment):
            raise RuntimeError("Refuse non-disposable PostgreSQL target")
        cls.admin_url = os.environ["DATABASE_URL"]
        cls.name = "aiops_core_reject_populated_ci"
        cls.url = urlunsplit((parsed.scheme, parsed.netloc, "/" + cls.name, "", ""))
        cls.created = False
        with psycopg.connect(cls.admin_url, autocommit=True) as admin:
            version = int(admin.execute("show server_version_num").fetchone()[0])
            if not 160000 <= version < 170000:
                raise RuntimeError("Requires PostgreSQL 16")
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(cls.name)))
            cls.created = True
        try:
            with psycopg.connect(cls.url) as db:
                for filename in MIGRATIONS:
                    db.execute((ROOT / "db/migrations" / filename).read_text())
            cls.temp = tempfile.TemporaryDirectory(prefix="core-reject-ci-")
            cls.proof_path = str(Path(cls.temp.name) / "owner-proofs.json")
            cls.owner_key = secrets.token_hex(48)
            cls.token_a = secrets.token_urlsafe(32)
            cls.token_b = secrets.token_urlsafe(32)
            def auth_entry(token, tenant):
                return {"token_sha256": hashlib.sha256(token.encode()).hexdigest(),
                        "actor_id": "svc-" + tenant, "tenant_ids": [tenant],
                        "permissions": ["hitl:reject:deliver"]}
            cls.env = patch.dict(os.environ, {
                "AIOPS_XREF_READ_AUTHZ_JSON": json.dumps([
                    auth_entry(cls.token_a, "TEN-A"),
                    auth_entry(cls.token_b, "TEN-B")]),
                "AIOPS_XREF_OWNER_ATTESTATION_KEY": cls.owner_key,
                "AIOPS_XREF_OWNER_PROOFS_PATH": cls.proof_path,
            })
            cls.env.start()
            cls.db_patch = patch.object(x, "db", side_effect=lambda: psycopg.connect(cls.url))
            cls.db_patch.start()
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
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
        # A failed/no-proof claim must not starve later tests in the same DB.
        with self.psycopg.connect(self.url) as db:
            db.execute("update aiops.hitl_decision_outbox set status='DEAD' "
                       "where status in ('PENDING','LEASED')")

    def _fixture(self):
        suffix = uuid.uuid4().hex
        ids = {k: k.upper() + "-" + suffix for k in
               ("run", "inc", "evidence", "analysis", "critique",
                "proposal", "approval", "event")}
        digest = hashlib.sha256(("SYNTHETIC-REJECT:" + suffix).encode()).hexdigest()
        evidence_ids = json.dumps([ids["evidence"]])
        with self.psycopg.connect(self.url) as db:
            db.execute("insert into aiops.incidents "
                       "(incident_id,title,severity,state,opened_at,source,synthetic) "
                       "values(%s,'synthetic reject','P4','OPEN',now(),'ci',true)",
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
                        ids["run"], evidence_ids,
                        json.dumps({"issues": [], "unsafe_actions": []})))
            db.execute("insert into aiops.action_proposals "
                       "(proposal_id,run_id,analysis_id,critique_id,source_action_id,"
                       "proposal_revision,target_ci_id,action_type,risk_tier,evidence_ids,"
                       "preconditions,expected_postconditions,proposal_hash,status,expires_at) "
                       "values(%s,%s,%s,%s,'CI-FIXTURE',1,'CI-SYNTHETIC',"
                       "'COLLECT_DIAGNOSTICS','LOW',%s,'[\"ci precondition\"]',"
                       "'[\"ci postcondition\"]',%s,'PROPOSED',now()+interval '1 hour')",
                       (ids["proposal"], ids["run"], ids["analysis"], ids["critique"],
                        evidence_ids, digest))
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
                       "values('run',%s,'TEN-A',%s,true,"
                       "now()-interval '10 seconds',now()-interval '5 seconds')",
                       (ids["run"], "SRC-" + suffix))
        self._write_proofs()
        return ids, digest

    def _write_proofs(self):
        with self.psycopg.connect(self.url) as db:
            rows = db.execute("select resource_kind,resource_id,tenant_id,verified,"
                              "source_event_id,observed_at,known_at "
                              "from aiops.tenant_resource_ownership").fetchall()
        proofs = {kind + "|" + rid: hmac.new(
            self.owner_key.encode(), x._owner_proof_payload(*row),
            hashlib.sha256).hexdigest()
            for row in rows for kind, rid in [row[:2]]}
        Path(self.proof_path).write_text(json.dumps({
            "schema": "aiops.core-ownership-proof.v1", "proofs": proofs}))

    def _post(self, suffix, body, token=None, tenant="TEN-A"):
        headers = {"Authorization": "Bearer " + (token or self.token_a)}
        # Exercise the real Core route handler and PostgreSQL transaction.
        # No httpx/TestClient dependency in the isolated PG16 CI job.
        if suffix == "claim":
            response = delivery.claim_reject(
                tenant, body, authorization=headers["Authorization"])
        else:
            event, sep, action = suffix.partition("/")
            if not sep or action != "ack":
                raise AssertionError("unexpected Core route")
            response = delivery.ack_reject(
                tenant, event, body, authorization=headers["Authorization"])
        return response.status_code, json.loads(response.body)

    def _claim(self, token=None, tenant="TEN-A"):
        return self._post("claim", {"owner": "svc-" + tenant, "limit": 1},
                          token=token, tenant=tenant)

    def _ack(self, ids, digest, token, *, owner="svc-TEN-A", tenant="TEN-A"):
        body = {"owner": owner, "run_id": ids["run"],
                "proposal_id": ids["proposal"], "proposal_hash": digest,
                "proposal_revision": 1, "lease_token": token,
                "execution_allowed": False, "effect_allowed": False}
        return self._post(ids["event"] + "/ack", body, tenant=tenant)

    def _no_effect(self):
        with self.psycopg.connect(self.url) as db:
            self.assertEqual(db.execute(
                "select count(*) from aiops.effect_receipts").fetchone()[0], 0)
            self.assertEqual(db.execute(
                "select count(*) from aiops.hitl_decision_outbox "
                "where decision='APPROVE'").fetchone()[0], 0)

    def test_concurrent_real_core_handler_one_lease(self):
        ids, digest = self._fixture()
        barrier = threading.Barrier(2)
        def contender():
            barrier.wait(timeout=10)
            return self._claim()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(contender) for _ in range(2)]
            results = [future.result(timeout=20) for future in futures]
        winners = [r[1]["items"][0] for r in results
                   if r[0] == 200 and r[1].get("status") == "LEASED"]
        self.assertEqual(len(winners), 1, results)
        self.assertEqual(winners[0]["event_id"], ids["event"])
        with self.psycopg.connect(self.url) as db:
            row = db.execute("select attempts,status from aiops.hitl_decision_outbox "
                             "where event_id=%s", (ids["event"],)).fetchone()
        self.assertEqual(row, (1, "LEASED"))
        self.assertEqual(self._ack(ids, digest, winners[0]["lease_token"])[1]["status"],
                         "DELIVERED")
        self._no_effect()

    def test_expired_lease_reclaim_and_stale_ack(self):
        ids, digest = self._fixture()
        code, claimed = self._claim()
        self.assertEqual((code, claimed["status"]), (200, "LEASED"))
        old = claimed["items"][0]["lease_token"]
        with self.psycopg.connect(self.url) as db:
            db.execute("update aiops.hitl_decision_outbox "
                       "set lease_until=now()-interval '1 second' where event_id=%s",
                       (ids["event"],))
        self.assertEqual(self._ack(ids, digest, old)[1]["status"], "UNKNOWN")
        _, reclaimed = self._claim()
        self.assertEqual(reclaimed["status"], "LEASED")
        new = reclaimed["items"][0]["lease_token"]
        self.assertNotEqual(new, old)
        self.assertEqual(self._ack(ids, digest, old)[1]["status"], "UNKNOWN")
        self.assertEqual(self._ack(ids, digest, new)[1]["status"], "DELIVERED")
        with self.psycopg.connect(self.url) as db:
            self.assertEqual(db.execute(
                "select attempts from aiops.hitl_decision_outbox where event_id=%s",
                (ids["event"],)).fetchone()[0], 2)
        self._no_effect()

    def test_ack_response_loss_replay_and_exact_eight_fields(self):
        ids, digest = self._fixture()
        _, claimed = self._claim()
        token = claimed["items"][0]["lease_token"]
        # Simulate the HTTP response being lost AFTER the DB transaction commits.
        self.assertEqual(self._ack(ids, digest, token)[1]["status"], "DELIVERED")
        _, replay = self._ack(ids, digest, token)
        self.assertEqual((replay["status"], replay["idempotent"]), ("DELIVERED", True))
        self.assertEqual(self._ack(ids, digest, "z" * 43)[1]["status"], "UNKNOWN")
        self.assertEqual(self._claim()[1]["items"], [])
        body = {"owner": "svc-TEN-A", "run_id": ids["run"],
                "proposal_id": ids["proposal"], "proposal_hash": digest,
                "proposal_revision": 1, "lease_token": token,
                "execution_allowed": False, "effect_allowed": False,
                "tenant_id": "TEN-A"}
        self.assertEqual(self._post(ids["event"] + "/ack", body)[1]["status"], "UNKNOWN")
        self._no_effect()

    def test_tenant_permission_and_independent_source_proof(self):
        ids, digest = self._fixture()
        code, _ = self._post("claim", {"owner": "svc-TEN-A", "limit": 1},
                             token=self.token_b)
        self.assertEqual(code, 403)
        self.assertEqual(self._post("claim", {"owner": "svc-TEN-A", "limit": 1},
                                    token="forged")[0], 401)
        # An immutable DB verified=true and source_event_id are NOT authority.
        Path(self.proof_path).write_text(json.dumps({
            "schema": "aiops.core-ownership-proof.v1", "proofs": {}}))
        _, denied = self._claim()
        self.assertEqual(denied["status"], "UNKNOWN")
        self.assertNotIn("run_id", denied)
        with self.psycopg.connect(self.url) as db:
            self.assertEqual(db.execute(
                "select attempts from aiops.hitl_decision_outbox where event_id=%s",
                (ids["event"],)).fetchone()[0], 0)
        self._write_proofs()
        _, allowed = self._claim()
        self.assertEqual(allowed["status"], "LEASED")
        self.assertEqual(self._ack(ids, digest, allowed["items"][0]["lease_token"])[1]["status"],
                         "DELIVERED")
        self._no_effect()

    def test_populated_migration_reapply_and_data_transaction_rollback(self):
        ids, _ = self._fixture()
        with self.psycopg.connect(self.url) as db:
            before = db.execute("select count(*) from aiops.hitl_decision_outbox").fetchone()[0]
            for filename in MIGRATIONS[2:]:
                db.execute((ROOT / "db/migrations" / filename).read_text())
            after = db.execute("select count(*) from aiops.hitl_decision_outbox").fetchone()[0]
            self.assertEqual(after, before)
        with self.psycopg.connect(self.url) as db:
            db.execute("update aiops.hitl_decision_outbox set status='DEAD' "
                       "where event_id=%s", (ids["event"],))
            db.rollback()
        with self.psycopg.connect(self.url) as db:
            self.assertEqual(db.execute(
                "select status from aiops.hitl_decision_outbox where event_id=%s",
                (ids["event"],)).fetchone()[0], "PENDING")
        # This proves rollback of a data transaction, NOT an actual downgrade
        # of persisted schema/data: no down migration exists or is invoked.
        self._no_effect()


if __name__ == "__main__":
    unittest.main()
