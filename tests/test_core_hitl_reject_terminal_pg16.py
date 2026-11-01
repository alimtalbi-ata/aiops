"""Core-owned atomic REJECT terminal handler against installed disposable PG16.

Synthetic ownership HMAC is only a fixture integrity fence, never GLPI rights.
No Worker file, external GLPI, human ALLOW, Temporal signal, executor or LIVE.
"""
import concurrent.futures
import hashlib
import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import test_core_hitl_reject_pg16_populated as base
from core import hitl_reject_delivery as delivery


class CoreTerminalPopulatedPG16(base.CoreRejectPopulatedPG16):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            with cls.psycopg.connect(cls.url) as db:
                for name in ("013_actor_delegation_replay_ledger.sql",
                             "014_hitl_reject_terminal_receipts.sql"):
                    db.execute((Path(__file__).resolve().parents[1] /
                                "db/migrations" / name).read_text())
            def entry(token, tenant):
                return {"token_sha256": hashlib.sha256(token.encode()).hexdigest(),
                        "actor_id": "svc-" + tenant, "tenant_ids": [tenant],
                        "permissions": ["hitl:reject:deliver", "hitl:reject:terminal"]}
            cls.terminal_env = patch.dict(os.environ, {
                "AIOPS_XREF_READ_AUTHZ_JSON": json.dumps([
                    entry(cls.token_a, "TEN-A"), entry(cls.token_b, "TEN-B")])
            })
            cls.terminal_env.start()
        except Exception:
            super().tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "terminal_env"):
            cls.terminal_env.stop()
        super().tearDownClass()

    def _dead(self, ids, digest, token, *, tenant="TEN-A", actor=None,
              changes=None, auth=None):
        body = {"owner": actor or "svc-" + tenant,
                "run_id": ids["run"], "proposal_id": ids["proposal"],
                "proposal_hash": digest, "proposal_revision": 1,
                "lease_token": token, "execution_allowed": False,
                "effect_allowed": False}
        body.update(changes or {})
        response = delivery.terminal_reject(
            tenant, ids["event"], body,
            authorization="Bearer " + (auth or self.token_a))
        return response.status_code, json.loads(response.body)

    def _exhaust(self):
        ids, digest = self._fixture()
        tokens = []
        for attempt in range(8):
            code, claimed = self._claim()
            self.assertEqual((code, claimed["status"]), (200, "LEASED"))
            tokens.append(claimed["items"][0]["lease_token"])
            with self.psycopg.connect(self.url) as db:
                db.execute("update aiops.hitl_decision_outbox "
                           "set lease_until=now()-interval '2 seconds' "
                           "where event_id=%s", (ids["event"],))
        self.assertEqual(self._claim()[1].get("items"), [])
        return ids, digest, tokens

    def test_terminal_atomic_and_ack_replay_denied(self):
        ids, digest, tokens = self._exhaust()
        code, result = self._dead(ids, digest, tokens[-1])
        self.assertEqual((code, result["status"], result["idempotent"]),
                         (200, "DEAD", False))
        self.assertEqual(result["attempts"], 8)
        self.assertEqual(result["receipt_schema"], delivery.TERMINAL_SCHEMA)
        self.assertRegex(result["receipt_sha256"], r"^[0-9a-f]{64}$")
        self.assertNotIn("lease_token", result)
        # Redacted machine-readable receipt binds actual Core/PG16 readback
        # to the checked-out exact HEAD, without bearer, token or event ID.
        target = os.environ.get("AIOPS_CORE_TERMINAL_RECEIPT_DIR")
        if target:
            path = Path(target)
            path.mkdir(parents=True, exist_ok=True)
            receipt = {
                "schema": "aiops.core-terminal-pg16-ci-receipt.v1",
                "source_head": os.environ["AIOPS_EXPECTED_HEAD_SHA"],
                "terminal_status": result["status"],
                "attempts": result["attempts"],
                "receipt_sha256": result["receipt_sha256"],
                "actor_authorization": "UNKNOWN",
                "human_glpi_attested": False,
                "execution_allowed": False,
                "effect_allowed": False,
                "synthetic_disposable": True,
            }
            receipt["payload_sha256"] = hashlib.sha256(json.dumps(
                receipt, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            (path / "terminal-dead.json").write_text(
                json.dumps(receipt, sort_keys=True, indent=2) + "\n")
        self.assertEqual(self._ack(ids, digest, tokens[-1])[1]["status"], "UNKNOWN")
        self.assertEqual(self._claim()[1]["items"], [])
        with self.psycopg.connect(self.url) as db:
            self.assertEqual(db.execute(
                "select status,attempts from aiops.hitl_decision_outbox "
                "where event_id=%s", (ids["event"],)).fetchone(), ("DEAD", 8))
            self.assertEqual(db.execute(
                "select count(*) from aiops.hitl_reject_terminal_receipts "
                "where event_id=%s", (ids["event"],)).fetchone()[0], 1)
        self._no_effect()

    def test_terminal_replay_idempotence_and_stale_token_denied(self):
        ids, digest, tokens = self._exhaust()
        first = self._dead(ids, digest, tokens[-1])[1]
        second = self._dead(ids, digest, tokens[-1])[1]
        self.assertEqual(second["status"], "DEAD")
        self.assertTrue(second["idempotent"])
        self.assertEqual(first["receipt_sha256"], second["receipt_sha256"])
        self.assertEqual(self._dead(ids, digest, tokens[0])[1]["status"], "UNKNOWN")
        self.assertEqual(self._dead(ids, digest, "z"*43)[1]["status"], "UNKNOWN")
        self.assertEqual(self._dead(ids, digest, tokens[-1],
                                   changes={"proposal_revision": 2})[1]["status"], "UNKNOWN")
        self.assertEqual(self._dead(ids, digest, tokens[-1],
                                   changes={"effect_allowed": True})[1]["status"], "UNKNOWN")
        self._no_effect()

    def test_terminal_concurrent_single_audit_row(self):
        ids, digest, tokens = self._exhaust()
        barrier = threading.Barrier(2)
        def contender():
            barrier.wait(timeout=10)
            return self._dead(ids, digest, tokens[-1])
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(contender) for _ in range(2)]
            results = [f.result(timeout=20) for f in futures]
        self.assertEqual([x[1]["status"] for x in results], ["DEAD", "DEAD"])
        self.assertEqual(sorted(x[1]["idempotent"] for x in results), [False, True])
        self.assertEqual(len({x[1]["receipt_sha256"] for x in results}), 1)
        with self.psycopg.connect(self.url) as db:
            self.assertEqual(db.execute(
                "select count(*) from aiops.hitl_reject_terminal_receipts "
                "where event_id=%s", (ids["event"],)).fetchone()[0], 1)
        self._no_effect()

    def test_terminal_tenant_permission_and_source_proof_fail_closed(self):
        ids, digest, tokens = self._exhaust()
        self.assertEqual(self._dead(ids, digest, tokens[-1], tenant="TEN-B",
                                   auth=self.token_b)[1]["status"], "UNKNOWN")
        self.assertEqual(self._dead(ids, digest, tokens[-1], auth="forged")[0], 401)
        self.assertEqual(self._dead(ids, digest, tokens[-1],
                                   changes={"owner": "svc-foreign"})[1]["status"], "UNKNOWN")
        with patch.dict(os.environ, {"AIOPS_XREF_READ_AUTHZ_JSON": json.dumps([{
            "token_sha256": hashlib.sha256(self.token_a.encode()).hexdigest(),
            "actor_id": "svc-TEN-A", "tenant_ids": ["TEN-A"],
            "permissions": ["hitl:reject:deliver"]}])}):
            self.assertEqual(self._dead(ids, digest, tokens[-1])[0], 403)
        Path(self.proof_path).write_text(json.dumps({
            "schema": "aiops.core-ownership-proof.v1", "proofs": {}}))
        self.assertEqual(self._dead(ids, digest, tokens[-1])[1]["status"], "UNKNOWN")
        with self.psycopg.connect(self.url) as db:
            self.assertEqual(db.execute(
                "select count(*) from aiops.hitl_reject_terminal_receipts "
                "where event_id=%s", (ids["event"],)).fetchone()[0], 0)
        self._write_proofs()
        self.assertEqual(self._dead(ids, digest, tokens[-1])[1]["status"], "DEAD")
        self._no_effect()

    def test_terminal_not_before_budget_or_expiry(self):
        ids, digest = self._fixture()
        _, claimed = self._claim()
        token = claimed["items"][0]["lease_token"]
        self.assertEqual(self._dead(ids, digest, token)[1]["status"], "UNKNOWN")
        with self.psycopg.connect(self.url) as db:
            db.execute("update aiops.hitl_decision_outbox "
                       "set attempts=8 where event_id=%s", (ids["event"],))
        self.assertEqual(self._dead(ids, digest, token)[1]["status"], "UNKNOWN")
        with self.psycopg.connect(self.url) as db:
            db.execute("update aiops.hitl_decision_outbox "
                       "set lease_until=now()-interval '2 seconds' where event_id=%s",
                       (ids["event"],))
        self.assertEqual(self._dead(ids, digest, token)[1]["status"], "DEAD")
        self._no_effect()

    def test_terminal_014_immutable_reapply_013_preserved_and_rollback(self):
        ids, digest, tokens = self._exhaust()
        with self.psycopg.connect(self.url) as db:
            db.execute("update aiops.hitl_decision_outbox set status='DEAD' "
                       "where event_id=%s", (ids["event"],))
            db.rollback()
        self.assertEqual(self._dead(ids, digest, tokens[-1])[1]["status"], "DEAD")
        with self.psycopg.connect(self.url) as db:
            db.execute((Path(__file__).resolve().parents[1] / "db/migrations" /
                        "014_hitl_reject_terminal_receipts.sql").read_text())
            self.assertEqual(db.execute(
                "select count(*) from aiops.hitl_reject_terminal_receipts "
                "where event_id=%s", (ids["event"],)).fetchone()[0], 1)
            self.assertIsNotNone(db.execute(
                "select to_regclass('aiops.actor_delegation_nonce_ledger')").fetchone()[0])
            self.assertIsNotNone(db.execute(
                "select to_regclass('aiops.actor_delegation_revocations')").fetchone()[0])
        for sql in (
            "update aiops.hitl_reject_terminal_receipts set attempts=9 where event_id=%s",
            "delete from aiops.hitl_reject_terminal_receipts where event_id=%s",
        ):
            with self.assertRaises(self.psycopg.Error):
                with self.psycopg.connect(self.url) as db:
                    db.execute(sql, (ids["event"],))
        self._no_effect()
