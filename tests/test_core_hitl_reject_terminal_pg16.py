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

    def test_terminal_native_pg16_restore_013_014_audit_and_replay(self):
        """Native PG16 custom archive into a NEW disposable DB, never source.

        Keep the archive ephemeral: it contains synthetic lease tokens, so
        only a redacted digest/row-count manifest may leave the CI runner.
        """
        import subprocess
        import tempfile
        from urllib.parse import urlsplit, urlunsplit

        client_dir = Path("/usr/lib/postgresql/16/bin")
        dump, restore = (str(client_dir / name)
                         for name in ("pg_dump", "pg_restore"))
        for binary in (dump, restore):
            self.assertTrue(Path(binary).is_file(),
                            "NOT_QUALIFIED: native PostgreSQL 16 client absent")
            version = subprocess.run(
                [binary, "--version"], check=True, capture_output=True,
                text=True, timeout=10).stdout
            self.assertIn("(PostgreSQL) 16.", version)
        parsed = urlsplit(self.url)
        self.assertEqual((parsed.hostname, parsed.port, parsed.username),
                         ("127.0.0.1", 5432, "aiops"))
        self.assertEqual(parsed.path, "/" + self.name)
        with self.psycopg.connect(self.url) as db:
            version = int(db.execute("show server_version_num").fetchone()[0])
            self.assertTrue(160000 <= version < 170000)

        ids, digest, tokens = self._exhaust()
        first = self._dead(ids, digest, tokens[-1])
        self.assertEqual((first[0], first[1]["status"]), (200, "DEAD"))
        hash_of = lambda s: hashlib.sha256(s.encode("utf-8")).hexdigest()
        issuer = "https://issuer.example.invalid"
        consumed_jti, revoked_jti = hash_of("terminal-native-consumed"), hash_of("terminal-native-revoked")
        with self.psycopg.connect(self.url) as db:
            self.assertTrue(db.execute(
                "select aiops.actor_delegation_consume(%s,%s,%s,%s,%s,%s,"
                "clock_timestamp()+interval '120 seconds')",
                ("TEN-A", issuer, hash_of("synthetic-subject"), consumed_jti,
                 hash_of("terminal-native-nonce"), hash_of(ids["run"]))).fetchone()[0])
            self.assertTrue(db.execute(
                "select aiops.actor_delegation_revoke(%s,%s,%s)",
                (issuer, revoked_jti, "SRC-TERMINAL-RESTORE")).fetchone()[0])

        def snapshot(url):
            with self.psycopg.connect(url) as db:
                return {
                    "terminal": db.execute(
                        "select event_id,tenant_id,run_id,proposal_hash,"
                        "receipt_payload,receipt_sha256 from "
                        "aiops.hitl_reject_terminal_receipts where event_id=%s",
                        (ids["event"],)).fetchall(),
                    "nonce": db.execute(
                        "select tenant_id,issuer,subject_sha256,jti_sha256,"
                        "nonce_sha256,resource_sha256,expires_at,consumed_at "
                        "from aiops.actor_delegation_nonce_ledger "
                        "where issuer=%s and jti_sha256=%s",
                        (issuer, consumed_jti)).fetchall(),
                    "revocation": db.execute(
                        "select issuer,jti_sha256,source_event_id,revoked_at "
                        "from aiops.actor_delegation_revocations "
                        "where issuer=%s and jti_sha256=%s",
                        (issuer, revoked_jti)).fetchall(),
                    "outbox": db.execute(
                        "select status,attempts,lease_owner,lease_token "
                        "from aiops.hitl_decision_outbox where event_id=%s",
                        (ids["event"],)).fetchall(),
                }
        before = snapshot(self.url)
        self.assertEqual([len(before[k]) for k in
                          ("terminal", "nonce", "revocation", "outbox")],
                         [1, 1, 1, 1])
        self.assertEqual(before["outbox"][0][:2], ("DEAD", 8))

        target_name = "aiops_core_terminal_native_restore_ci"
        target_url = urlunsplit((parsed.scheme, parsed.netloc,
                                 "/" + target_name, "", ""))
        created = False
        try:
            with self.psycopg.connect(self.admin_url, autocommit=True) as admin:
                admin.execute(self.sql.SQL("create database {}").format(
                    self.sql.Identifier(target_name)))
                created = True
            with tempfile.TemporaryDirectory(prefix="core-terminal-native-pg16-") as tmp:
                archive = Path(tmp) / "terminal-013-014.pgcustom"
                env = dict(os.environ)
                env["PGCONNECT_TIMEOUT"] = "5"
                subprocess.run(
                    [dump, "--format=custom", "--no-owner", "--no-acl",
                     "--file=" + str(archive), "--dbname=" + self.url],
                    env=env, check=True, timeout=90, stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE)
                self.assertGreater(archive.stat().st_size, 1000)
                expected = hashlib.sha256(archive.read_bytes()).hexdigest()
                tampered = Path(tmp) / "corrupt.pgcustom"
                tampered.write_bytes(archive.read_bytes() + b"tampered")
                self.assertNotEqual(hashlib.sha256(tampered.read_bytes()).hexdigest(),
                                    expected)
                # Fail before invoking pg_restore if the archive digest differs.
                def verified(path):
                    actual = hashlib.sha256(path.read_bytes()).hexdigest()
                    if actual != expected:
                        raise ValueError("archive SHA256 mismatch")
                    return path
                with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                    verified(tampered)
                subprocess.run(
                    [restore, "--no-owner", "--no-acl", "--single-transaction",
                     "--exit-on-error", "--dbname=" + target_url,
                     str(verified(archive))],
                    env=env, check=True, timeout=120,
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(),
                                 expected)
                self.assertEqual(snapshot(target_url), before)
                with self.psycopg.connect(target_url) as db:
                    self.assertFalse(db.execute(
                        "select aiops.actor_delegation_consume(%s,%s,%s,%s,%s,%s,"
                        "clock_timestamp()+interval '120 seconds')",
                        ("TEN-A", issuer, hash_of("synthetic-subject"), consumed_jti,
                         hash_of("fresh-nonce"), hash_of(ids["run"]))).fetchone()[0])
                    self.assertFalse(db.execute(
                        "select aiops.actor_delegation_consume(%s,%s,%s,%s,%s,%s,"
                        "clock_timestamp()+interval '120 seconds')",
                        ("TEN-A", issuer, hash_of("synthetic-subject"), revoked_jti,
                         hash_of("other-nonce"), hash_of(ids["run"]))).fetchone()[0])
                    # Idempotent 013/014 reapply must not erase audit rows.
                    for name in ("013_actor_delegation_replay_ledger.sql",
                                 "014_hitl_reject_terminal_receipts.sql"):
                        db.execute((Path(__file__).resolve().parents[1] /
                                    "db/migrations" / name).read_text())
                self.assertEqual(snapshot(target_url), before)
                for statement, params in (
                    ("update aiops.hitl_reject_terminal_receipts "
                     "set attempts=9 where event_id=%s", (ids["event"],)),
                    ("delete from aiops.actor_delegation_revocations "
                     "where issuer=%s and jti_sha256=%s",
                     (issuer, revoked_jti)),
                ):
                    with self.assertRaises(self.psycopg.Error):
                        with self.psycopg.connect(target_url) as db:
                            db.execute(statement, params)
                self.assertEqual(snapshot(target_url), before)
                out = os.environ.get("AIOPS_CORE_TERMINAL_RECEIPT_DIR")
                self.assertTrue(out, "CI must retain redacted restore manifest")
                receipt_dir = Path(out)
                receipt_dir.mkdir(parents=True, exist_ok=True)
                manifest = {
                    "schema": "aiops.core-terminal-native-restore-ci.v1",
                    "source_head": os.environ["AIOPS_EXPECTED_HEAD_SHA"],
                    "postgres_server_major": 16,
                    "pg_dump_major": 16, "pg_restore_major": 16,
                    "installed": ["001", "004", "009", "010", "011",
                                  "012", "013", "014"],
                    "archive_sha256": expected,
                    "audit_rows_preserved": {"terminal_014": 1,
                                             "nonce_013": 1,
                                             "revocation_013": 1},
                    "archive_retained": False,
                    "restored_to_new_disposable_database": True,
                    "actor_authorization": "UNKNOWN",
                    "execution_allowed": False, "effect_allowed": False,
                    "rollback": "CODE_ONLY_KEEP_013_014_AUDIT",
                }
                manifest["payload_sha256"] = hashlib.sha256(
                    json.dumps(manifest, sort_keys=True,
                               separators=(",", ":")).encode()).hexdigest()
                (receipt_dir / "terminal-native-restore.json").write_text(
                    json.dumps(manifest, sort_keys=True, indent=2) + "\n")
        finally:
            if created:
                with self.psycopg.connect(self.admin_url, autocommit=True) as admin:
                    admin.execute(self.sql.SQL(
                        "drop database {} with (force)").format(
                            self.sql.Identifier(target_name)))
        # Source is never dropped or downgraded; both audit ledgers survive.
        self.assertEqual(snapshot(self.url), before)
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

    def _canonical_core_client(self):
        """Exercise the shipped Core FastAPI app, not a test-only router."""
        import importlib
        from fastapi.testclient import TestClient
        with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "synthetic-ci-core-only"}):
            core_main = importlib.import_module("core.main")
        route = "/api/tenants/{tenant_id}/hitl/reject-delivery/{event_id}/dead"
        self.assertIn(route, [r.path for r in core_main.app.routes])
        return TestClient(core_main.app)

    def test_terminal_canonical_core_http_worker_contract_and_receipt(self):
        ids, digest, tokens = self._exhaust()
        client = self._canonical_core_client()
        path = f"/api/tenants/TEN-A/hitl/reject-delivery/{ids['event']}/dead"
        body = {
            "owner": "svc-TEN-A", "run_id": ids["run"],
            "proposal_id": ids["proposal"], "proposal_hash": digest,
            "proposal_revision": 1, "lease_token": tokens[-1],
            "execution_allowed": False, "effect_allowed": False,
        }
        headers = {"Authorization": "Bearer " + self.token_a}
        self.assertEqual(client.post(path, json=body).status_code, 401)
        self.assertEqual(client.post(path, json=body, headers={
            "Authorization": "Bearer " + self.token_b}).status_code, 403)
        wrong_tenant = client.post(
            path.replace("/TEN-A/", "/TEN-B/"),
            json={**body, "owner": "svc-TEN-B"},
            headers={"Authorization": "Bearer " + self.token_b})
        self.assertEqual((wrong_tenant.status_code, wrong_tenant.json()["status"]),
                         (200, "UNKNOWN"))
        for changed in (
            {"run_id": "RUN-foreign"},
            {"proposal_id": "PROPOSAL-foreign"},
            {"proposal_hash": "0" * 64},
            {"proposal_revision": 2},
            {"lease_token": tokens[0]},
            {"effect_allowed": True},
        ):
            denied = client.post(path, json={**body, **changed}, headers=headers)
            self.assertEqual((denied.status_code, denied.json()["status"]),
                             (200, "UNKNOWN"))
            self.assertFalse(denied.json()["effect_allowed"])
        with self.psycopg.connect(self.url) as db:
            self.assertEqual(db.execute(
                "select status,attempts from aiops.hitl_decision_outbox "
                "where event_id=%s", (ids["event"],)).fetchone(), ("LEASED", 8))
            self.assertEqual(db.execute(
                "select count(*) from aiops.hitl_reject_terminal_receipts "
                "where event_id=%s", (ids["event"],)).fetchone()[0], 0)

        success = client.post(path, json=body, headers=headers)
        replay = client.post(path, json=body, headers=headers)
        ack = client.post(path.removesuffix("/dead") + "/ack", json=body, headers=headers)
        self.assertEqual((success.status_code, success.json()["status"],
                          success.json()["idempotent"]), (200, "DEAD", False))
        self.assertEqual((replay.status_code, replay.json()["status"],
                          replay.json()["idempotent"]), (200, "DEAD", True))
        self.assertEqual((ack.status_code, ack.json()["status"]), (200, "UNKNOWN"))
        self.assertEqual(success.json()["receipt_sha256"],
                         replay.json()["receipt_sha256"])
        self.assertFalse(success.json()["execution_allowed"])
        self.assertFalse(success.json()["effect_allowed"])
        self.assertNotIn(tokens[-1], success.text)
        self.assertNotIn("ALLOW", success.text)
        with self.psycopg.connect(self.url) as db:
            stored = db.execute(
                "select receipt_payload,receipt_sha256 from "
                "aiops.hitl_reject_terminal_receipts where event_id=%s",
                (ids["event"],)).fetchall()
            self.assertEqual(len(stored), 1)
            receipt, receipt_sha = stored[0]
            self.assertEqual(receipt["tenant_id"], "TEN-A")
            self.assertEqual(receipt["run_id"], ids["run"])
            self.assertEqual(receipt["proposal_hash"], digest)
            self.assertEqual(receipt["lease_owner"], "svc-TEN-A")
            self.assertEqual(receipt["lease_token_sha256"],
                             hashlib.sha256(tokens[-1].encode()).hexdigest())
            self.assertEqual(receipt_sha, success.json()["receipt_sha256"])
            self.assertEqual(receipt_sha, delivery._terminal_digest(
                delivery._terminal_json(receipt)))
            self.assertNotIn(tokens[-1], json.dumps(receipt))
            self.assertEqual(db.execute(
                "select status,attempts from aiops.hitl_decision_outbox "
                "where event_id=%s", (ids["event"],)).fetchone(), ("DEAD", 8))
        target = os.environ.get("AIOPS_CORE_TERMINAL_RECEIPT_DIR")
        if target:
            path_out = Path(target)
            path_out.mkdir(parents=True, exist_ok=True)
            redacted = {
                "schema": "aiops.core-terminal-main-http-contract.v1",
                "source_head": os.environ["AIOPS_EXPECTED_HEAD_SHA"],
                "core_app_route_registered": True,
                "http": {"unauthenticated": 401, "wrong_tenant_permission": 403,
                         "foreign_tenant_non_enumerating": 200,
                         "mismatched_bindings": 6, "dead": 200,
                         "idempotent_replay": 200, "late_ack": 200},
                "terminal_status": "DEAD", "late_ack_status": "UNKNOWN",
                "audit_014_rows": 1, "attempts": 8,
                "receipt_sha256": receipt_sha,
                "human_glpi_attested": False, "actor_authorization": "UNKNOWN",
                "execution_allowed": False, "effect_allowed": False,
                "synthetic_disposable": True,
            }
            redacted["payload_sha256"] = hashlib.sha256(
                json.dumps(redacted, sort_keys=True,
                           separators=(",", ":")).encode()).hexdigest()
            (path_out / "terminal-main-http-contract.json").write_text(
                json.dumps(redacted, sort_keys=True, indent=2) + "\n")
        self._no_effect()

    def test_terminal_canonical_http_postcommit_revocation_fails_closed(self):
        """Committed DEAD survives service/provenance revocation; no replay grant."""
        ids, digest, tokens = self._exhaust()
        client = self._canonical_core_client()
        path = f"/api/tenants/TEN-A/hitl/reject-delivery/{ids['event']}/dead"
        ack_path = path.removesuffix("/dead") + "/ack"
        body = {"owner": "svc-TEN-A", "run_id": ids["run"],
                "proposal_id": ids["proposal"], "proposal_hash": digest,
                "proposal_revision": 1, "lease_token": tokens[-1],
                "execution_allowed": False, "effect_allowed": False}
        headers = {"Authorization": "Bearer " + self.token_a}
        first = client.post(path, json=body, headers=headers)
        self.assertEqual((first.status_code, first.json()["status"],
                          first.json()["idempotent"]), (200, "DEAD", False))
        receipt_hash = first.json()["receipt_sha256"]

        # Revoke the service credential after commit: a matching token/lease
        # must not be treated as a durable authorization.
        other_actor = [{"token_sha256": hashlib.sha256(self.token_b.encode()).hexdigest(),
                        "actor_id": "svc-TEN-B", "tenant_ids": ["TEN-B"],
                        "permissions": ["hitl:reject:deliver", "hitl:reject:terminal"]}]
        with patch.dict(os.environ, {
            "AIOPS_XREF_READ_AUTHZ_JSON": json.dumps(other_actor)}):
            revoked = client.post(path, json=body, headers=headers)
            self.assertEqual(revoked.status_code, 401)
            self.assertEqual(revoked.json()["status"], "UNKNOWN")
        # A still-recognized actor without the terminal permission is 403.
        restricted = [{"token_sha256": hashlib.sha256(self.token_a.encode()).hexdigest(),
                       "actor_id": "svc-TEN-A", "tenant_ids": ["TEN-A"],
                       "permissions": ["hitl:reject:deliver"]}]
        with patch.dict(os.environ, {"AIOPS_XREF_READ_AUTHZ_JSON": json.dumps(restricted)}):
            forbidden = client.post(path, json=body, headers=headers)
            self.assertEqual((forbidden.status_code, forbidden.json()["status"]),
                             (403, "UNKNOWN"))

        # Revoke independent run ownership provenance; even a previously
        # committed DEAD must not bypass the fresh source proof on replay.
        Path(self.proof_path).write_text(json.dumps({
            "schema": "aiops.core-ownership-proof.v1", "proofs": {}}))
        stale = client.post(path, json=body, headers=headers)
        self.assertEqual((stale.status_code, stale.json()["status"]), (200, "UNKNOWN"))
        late_ack = client.post(ack_path, json=body, headers=headers)
        self.assertEqual((late_ack.status_code, late_ack.json()["status"]),
                         (200, "UNKNOWN"))
        with self.psycopg.connect(self.url) as db:
            self.assertEqual(db.execute(
                "select status,attempts from aiops.hitl_decision_outbox "
                "where event_id=%s", (ids["event"],)).fetchone(), ("DEAD", 8))
            audit = db.execute(
                "select receipt_sha256 from aiops.hitl_reject_terminal_receipts "
                "where event_id=%s", (ids["event"],)).fetchall()
            self.assertEqual(audit, [(receipt_hash,)])
        self._write_proofs()
        replay = client.post(path, json=body, headers=headers)
        self.assertEqual((replay.status_code, replay.json()["status"],
                          replay.json()["idempotent"]), (200, "DEAD", True))
        self.assertEqual(replay.json()["receipt_sha256"], receipt_hash)
        with self.psycopg.connect(self.url) as db:
            self.assertEqual(db.execute(
                "select count(*) from aiops.hitl_reject_terminal_receipts "
                "where event_id=%s", (ids["event"],)).fetchone()[0], 1)

        target = os.environ.get("AIOPS_CORE_TERMINAL_RECEIPT_DIR")
        if target:
            path_out = Path(target)
            path_out.mkdir(parents=True, exist_ok=True)
            redacted = {
                "schema": "aiops.core-terminal-postcommit-revocation.v1",
                "source_head": os.environ["AIOPS_EXPECTED_HEAD_SHA"],
                "canonical_core_app": True, "synthetic_disposable": True,
                "http": {"committed_dead": 200, "credential_revoked": 401,
                         "terminal_permission_revoked": 403,
                         "source_proof_revoked": 200, "late_ack": 200,
                         "revalidated_idempotent_replay": 200},
                "revoked_status": "UNKNOWN", "late_ack_status": "UNKNOWN",
                "terminal_status": "DEAD", "attempts": 8,
                "audit_014_rows": 1, "receipt_sha256": receipt_hash,
                "actor_authorization": "UNKNOWN", "human_glpi_attested": False,
                "execution_allowed": False, "effect_allowed": False,
                "rollback": "CODE_ONLY_KEEP_013_014_AUDIT",
            }
            redacted["payload_sha256"] = hashlib.sha256(
                json.dumps(redacted, sort_keys=True,
                           separators=(",", ":")).encode()).hexdigest()
            (path_out / "terminal-postcommit-revocation.json").write_text(
                json.dumps(redacted, sort_keys=True, indent=2) + "\n")
        self._no_effect()

    def test_graph005_interleaved_terminal_dead_015_restore(self):
        """Core-owned joined regression, not a production Worker/GLPI assertion.

        The real Core HTTP writer appends seven pinned graph005 SOURCE events
        interleaved with synthetic Worker-shaped observations on the SAME Run
        as a real Core REJECT outbox -> terminal 014 DEAD transaction.
        Two real Worker OS processes are covered by the separate Policy gate.
        """
        import subprocess
        import tempfile
        from urllib.parse import urlsplit, urlunsplit
        from fastapi.testclient import TestClient
        import test_core_actor_canonical_seven_pg16 as fixture
        from core import actor_canonical_seven_source as binding
        from core import canonical_seven_pg_source as source
        internal = "ci-core-graph005-terminal-only-token-0123456789"
        with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": internal}):
            from core import main

        ids, digest, tokens = self._exhaust()
        pinned = json.loads((Path(__file__).resolve().parents[1] /
            "docs/customer-story/ACME-CORE015-V3-CANONICAL-NEGATIVE-2026-11-02.json"
            ).read_text(encoding="utf-8"))
        expected = tuple((e["source_event_id"], e["acme_full_event_sha256"],
                          e["acme_local_payload_sha256"]) for e in pinned["events"])
        self.assertEqual(len(expected), 7)
        self.assertEqual(len({e[0] for e in expected}), 7)
        tenant, actor = "TEN-A", "idp|graph005-terminal-ci"
        actor_issuer = fixture.ISSUER
        source_issuer = "core-graph005-disposable-source"
        scope = dict(tenant_id=tenant, incident_id=ids["inc"],
                     run_id=ids["run"], glpi_instance_id="GLPI-GRAPH-CORE",
                     ticket_id="777", glpi_entity_id="33",
                     permission="run:read", actor_subject=actor,
                     actor_issuer=actor_issuer)
        migration = (Path(__file__).resolve().parents[1] /
                     "db/migrations/015_core_run_event_idempotency.sql").read_text()
        with self.psycopg.connect(self.url) as db:
            self.assertIsNone(db.execute(
                "select 1 from information_schema.columns where "
                "table_schema='aiops' and table_name='run_events' "
                "and column_name='event_key'").fetchone())
            db.execute(migration)
            db.rollback()
        with self.psycopg.connect(self.url) as db:
            self.assertIsNone(db.execute(
                "select 1 from information_schema.columns where "
                "table_schema='aiops' and table_name='run_events' "
                "and column_name='event_key'").fetchone())
            db.execute(migration)
            db.execute(migration)
            db.execute("create table public.ci_actor_source_grants ("
                       "issuer text not null,actor_subject text not null,"
                       "tenant_id text not null,run_id text not null,"
                       "incident_id text not null,glpi_instance_id text not null,"
                       "ticket_id text not null,glpi_entity_id text not null,"
                       "permission text not null,expires_at timestamptz not null,"
                       "revoked boolean not null default false)")
            db.execute("update aiops.incidents set payload=%s::jsonb "
                       "where incident_id=%s",
                       (json.dumps({"tenant_id": tenant}), ids["inc"]))
            db.execute("insert into public.ci_actor_source_grants "
                       "(issuer,actor_subject,tenant_id,run_id,incident_id,"
                       "glpi_instance_id,ticket_id,glpi_entity_id,permission,"
                       "expires_at,revoked) values"
                       "(%s,%s,%s,%s,%s,%s,%s,%s,'run:read',"
                       "clock_timestamp()+interval '3 minutes',false)",
                       (actor_issuer, actor, tenant, ids["run"], ids["inc"],
                        scope["glpi_instance_id"], scope["ticket_id"],
                        scope["glpi_entity_id"]))
            for kind, rid in (("incident", ids["inc"]),
                              ("glpi_instance", scope["glpi_instance_id"]),
                              ("glpi_ticket", "GLPI-GRAPH-CORE:777"),
                              ("glpi_entity", "GLPI-GRAPH-CORE:33")):
                db.execute("insert into aiops.tenant_resource_ownership "
                           "(resource_kind,resource_id,tenant_id,source_event_id,"
                           "verified,observed_at,known_at) values"
                           "(%s,%s,%s,'CI-GRAPH005-OWN',true,"
                           "clock_timestamp()-interval '20 seconds',"
                           "clock_timestamp()-interval '10 seconds')",
                           (kind, rid, tenant))
            for ordinal, (event_id, full_sha, payload_sha) in enumerate(expected, 1):
                payload = dict(tenant_id=tenant, incident_id=ids["inc"],
                    run_id=ids["run"], ticket_id="777", glpi_entity_id="33",
                    source_event_id=event_id, sequence=ordinal,
                    actor_subject=actor, actor_issuer=actor_issuer,
                    source_issuer=source_issuer, synthetic=True,
                    graph_version=pinned["graph_version"],
                    acme_full_event_sha256=full_sha,
                    acme_local_payload_sha256=payload_sha)
                provenance = dict(tenant_id=tenant, incident_id=ids["inc"],
                                  run_id=ids["run"], actor_subject=actor,
                                  actor_issuer=actor_issuer,
                                  source_issuer=source_issuer)
                db.execute("insert into aiops.evidence "
                           "(evidence_id,source,external_id,observed_at,known_at,"
                           "claim,confidence,provenance,payload_hash,payload)"
                           " values(%s,%s,%s,clock_timestamp()-interval '20 seconds',"
                           "clock_timestamp()-interval '10 seconds','TEST_ONLY',1,"
                           "%s::jsonb,%s,%s::jsonb)",
                           (f"EVI-CORE-GRAPH-{ordinal:02d}", fixture.SOURCE,
                            event_id, json.dumps(provenance),
                            binding._digest(binding.PAYLOAD_DOMAIN, payload),
                            json.dumps(payload)))
            # Durable 013 facts are fixture-only and never human IdP grants.
            hashval = lambda s: hashlib.sha256(s.encode()).hexdigest()
            nonce_jti = hashval(ids["event"] + ":nonce")
            revoke_jti = hashval(ids["event"] + ":revoked")
            self.assertTrue(db.execute(
                "select aiops.actor_delegation_consume(%s,%s,%s,%s,%s,%s,%s)",
                (tenant, actor_issuer, hashval(actor), nonce_jti,
                 hashval(ids["event"] + ":nonce-value"),
                 hashval(ids["run"]), datetime.now(timezone.utc) +
                 timedelta(minutes=2))).fetchone()[0])
            self.assertTrue(db.execute(
                "select aiops.actor_delegation_revoke(%s,%s,%s)",
                (actor_issuer, revoke_jti, "CI-GRAPH005-REVOKED")).fetchone()[0])
        self._write_proofs()

        def read(request=None, issuer=source_issuer, db_url=None):
            with self.psycopg.connect(db_url or self.url) as db:
                return source.read_graph005_core_written_seven(
                    db, request or scope, source=fixture.SOURCE, issuer=issuer,
                    now=datetime.now(timezone.utc), expected_events=expected,
                    graph_version=pinned["graph_version"])

        bodies = {}
        with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": internal}), \
             patch.object(main, "ADMIN", internal), \
             patch.object(main, "db", side_effect=lambda: self.psycopg.connect(self.url)):
            with TestClient(main.app) as client:
                def append(version, stage, etype, status, key, evidence, payload,
                           decision=None):
                    body = dict(expected_version=version, stage=stage,
                                event_type=etype, status=status, event_key=key,
                                evidence_ids=evidence, decision=decision,
                                payload=payload)
                    response = client.post(f"/api/runs/{ids['run']}/events",
                        json=body, headers={"Authorization": "Bearer " + internal})
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(response.json()["sequence"], version)
                    self.assertFalse(response.json()["idempotent"])
                    return body

                for ordinal in range(1, 8):
                    if ordinal == 3:
                        append(3, "DGX_ANALYST", "WORKFLOW_OBSERVATION",
                               "PASS", "core-ci-graph005-analyst", [],
                               {"synthetic": True, "analysis": "UNVERIFIED"})
                    if ordinal == 6:
                        append(7, "VERIFY", "WORKFLOW_OBSERVATION",
                               "BLOCKED", "core-ci-graph005-verify", [],
                               {"synthetic": True, "verification": "UNVERIFIED"},
                               "UNVERIFIED")
                    physical = (1, 2, 4, 5, 6, 8, 9)[ordinal - 1]
                    event_id = expected[ordinal - 1][0]
                    with self.psycopg.connect(self.url) as db:
                        payload = db.execute(
                            "select payload from aiops.evidence where external_id=%s",
                            (event_id,)).fetchone()[0]
                    bodies[ordinal] = append(
                        physical, "SOURCE", "OBSERVED", "PASS", event_id,
                        [f"EVI-CORE-GRAPH-{ordinal:02d}"], payload)
                proof = read()
                self.assertIsNotNone(proof)
                self.assertEqual([e["sequence"] for e in proof["events"]],
                                 [1, 2, 4, 5, 6, 8, 9])
                self.assertEqual([e["payload"]["sequence"] for e in proof["events"]],
                                 list(range(1, 8)))
                self.assertTrue(all(e["full_event_hash"] != e["payload_hash"]
                                    for e in proof["events"]))
                for delta in ({"tenant_id": "TEN-FOREIGN"},
                              {"actor_subject": "idp|foreign"},
                              {"actor_issuer": "https://foreign.invalid"},
                              {"incident_id": "INC-FOREIGN"},
                              {"run_id": "RUN-FOREIGN"},
                              {"ticket_id": "778"}):
                    self.assertIsNone(read({**scope, **delta}))
                self.assertIsNone(read(issuer="forged-source-issuer"))
                with self.psycopg.connect(self.url) as db:
                    db.execute("update public.ci_actor_source_grants "
                               "set expires_at=clock_timestamp()-interval '1 second' "
                               "where run_id=%s", (ids["run"],))
                self.assertIsNone(read())
                with self.psycopg.connect(self.url) as db:
                    db.execute("update public.ci_actor_source_grants "
                               "set expires_at=clock_timestamp()+interval '3 minutes' "
                               "where run_id=%s", (ids["run"],))
                self.assertIsNotNone(read())

                append(10, "HITL", "WORKFLOW_OBSERVATION", "BLOCKED",
                       "core-ci-graph005-reject", [],
                       {"synthetic": True, "reopen": "RECOMMENDED_NOT_EXECUTED",
                        "execution_allowed": False, "effect_allowed": False},
                       "REJECT")
                self.assertIsNotNone(read())
                dead_path = (f"/api/tenants/TEN-A/hitl/reject-delivery/"
                             f"{ids['event']}/dead")
                dead_body = dict(owner="svc-TEN-A", run_id=ids["run"],
                    proposal_id=ids["proposal"], proposal_hash=digest,
                    proposal_revision=1, lease_token=tokens[-1],
                    execution_allowed=False, effect_allowed=False)
                dead_headers = {"Authorization": "Bearer " + self.token_a}
                self.assertEqual(client.post(dead_path, json=dead_body).status_code,
                                 401)
                # HMAC ownership is a signed synthetic Core integrity fence,
                # NOT a human IdP assertion. A forged signed Run must not
                # terminalize an exhausted outbox or create an 014 audit row.
                proof_file = Path(self.proof_path)
                signed = json.loads(proof_file.read_text())
                proof_key = "run|" + ids["run"]
                self.assertIn(proof_key, signed["proofs"])
                original_mac = signed["proofs"][proof_key]
                signed["proofs"][proof_key] = (
                    "0" * 64 if original_mac != "0" * 64 else "1" * 64)
                proof_file.write_text(json.dumps(signed))
                forged = client.post(dead_path, json=dead_body,
                                     headers=dead_headers)
                self.assertEqual((forged.status_code, forged.json()["status"]),
                                 (200, "UNKNOWN"))
                with self.psycopg.connect(self.url) as db:
                    self.assertEqual(db.execute(
                        "select status,attempts from aiops.hitl_decision_outbox "
                        "where event_id=%s", (ids["event"],)).fetchone(),
                        ("LEASED", 8))
                    self.assertEqual(db.execute(
                        "select count(*) from aiops.hitl_reject_terminal_receipts "
                        "where event_id=%s", (ids["event"],)).fetchone()[0], 0)
                self._write_proofs()
                first = client.post(dead_path, json=dead_body,
                                    headers=dead_headers)
                self.assertEqual((first.status_code, first.json()["status"],
                                  first.json()["idempotent"]), (200, "DEAD", False))
                receipt_sha = first.json()["receipt_sha256"]
                self.assertRegex(receipt_sha, r"^[0-9a-f]{64}$")
                with self.psycopg.connect(self.url) as db:
                    db.execute("update public.ci_actor_source_grants "
                               "set revoked=true where run_id=%s", (ids["run"],))
                self.assertIsNone(read())
                repeated = client.post(dead_path, json=dead_body,
                                       headers=dead_headers)
                self.assertEqual((repeated.status_code, repeated.json()["status"],
                                  repeated.json()["idempotent"]),
                                 (200, "DEAD", True))
                self.assertEqual(repeated.json()["receipt_sha256"], receipt_sha)
                replay = client.post(f"/api/runs/{ids['run']}/events",
                    json=bodies[1],
                    headers={"Authorization": "Bearer " + internal})
                self.assertEqual((replay.status_code, replay.json()["idempotent"],
                                  replay.json()["sequence"]), (200, True, 1))
                late = client.post(dead_path.removesuffix("/dead") + "/ack",
                                   json=dead_body, headers=dead_headers)
                self.assertEqual(late.json()["status"], "UNKNOWN")

        def snapshot(db_url):
            with self.psycopg.connect(db_url) as db:
                return {
                    "source": db.execute(
                        "select sequence,event_key from aiops.run_events "
                        "where run_id=%s and stage='SOURCE' order by sequence",
                        (ids["run"],)).fetchall(),
                    "all_events": db.execute(
                        "select sequence,stage from aiops.run_events "
                        "where run_id=%s order by sequence",
                        (ids["run"],)).fetchall(),
                    "outbox": db.execute(
                        "select status,attempts from aiops.hitl_decision_outbox "
                        "where event_id=%s", (ids["event"],)).fetchone(),
                    "audit_014": db.execute(
                        "select receipt_sha256 from aiops.hitl_reject_terminal_receipts "
                        "where event_id=%s", (ids["event"],)).fetchall(),
                    "nonce_013": db.execute(
                        "select count(*) from aiops.actor_delegation_nonce_ledger "
                        "where issuer=%s and jti_sha256=%s",
                        (actor_issuer, nonce_jti)).fetchone()[0],
                    "revocation_013": db.execute(
                        "select count(*) from aiops.actor_delegation_revocations "
                        "where issuer=%s and jti_sha256=%s",
                        (actor_issuer, revoke_jti)).fetchone()[0],
                    "effects": db.execute(
                        "select count(*) from aiops.effect_receipts").fetchone()[0],
                    "approves": db.execute(
                        "select count(*) from aiops.hitl_decision_outbox "
                        "where decision='APPROVE'").fetchone()[0],
                }
        before = snapshot(self.url)
        self.assertEqual(before["source"], list(zip(
            [1, 2, 4, 5, 6, 8, 9], [e[0] for e in expected])))
        self.assertEqual(before["all_events"], [
            (1, "SOURCE"), (2, "SOURCE"), (3, "DGX_ANALYST"),
            (4, "SOURCE"), (5, "SOURCE"), (6, "SOURCE"),
            (7, "VERIFY"), (8, "SOURCE"), (9, "SOURCE"),
            (10, "HITL")])
        self.assertEqual(before["outbox"], ("DEAD", 8))
        self.assertEqual(before["audit_014"], [(receipt_sha,)])
        self.assertEqual((before["nonce_013"], before["revocation_013"]), (1, 1))
        self.assertEqual((before["effects"], before["approves"]), (0, 0))
        with self.psycopg.connect(self.url) as db:
            db.execute(migration)
        self.assertEqual(snapshot(self.url), before)
        for statement, params in (
            ("update aiops.hitl_reject_terminal_receipts set attempts=9 "
             "where event_id=%s", (ids["event"],)),
            ("delete from aiops.hitl_reject_terminal_receipts "
             "where event_id=%s", (ids["event"],)),
            ("delete from aiops.actor_delegation_nonce_ledger "
             "where issuer=%s and jti_sha256=%s", (actor_issuer, nonce_jti)),
            ("update aiops.actor_delegation_revocations set "
             "source_event_id='FORGED' where issuer=%s and jti_sha256=%s",
             (actor_issuer, revoke_jti)),
        ):
            with self.assertRaises(self.psycopg.Error):
                with self.psycopg.connect(self.url) as db:
                    db.execute(statement, params)
        self.assertEqual(snapshot(self.url), before)

        parsed = urlsplit(self.url)
        restore_name = "aiops_core_graph005_dead_restore_ci"
        restore_url = urlunsplit((parsed.scheme, parsed.netloc,
                                 "/" + restore_name, "", ""))
        client_bin = Path("/usr/lib/postgresql/16/bin")
        for binary in ("pg_dump", "pg_restore"):
            self.assertIn("(PostgreSQL) 16.", subprocess.run(
                [str(client_bin / binary), "--version"], check=True,
                capture_output=True, text=True, timeout=10).stdout)
        created = False
        try:
            with self.psycopg.connect(self.admin_url, autocommit=True) as admin:
                admin.execute(self.sql.SQL("create database {}").format(
                    self.sql.Identifier(restore_name)))
                created = True
            with tempfile.TemporaryDirectory(prefix="core-graph005-dead-ci-") as tmp:
                archive = Path(tmp) / "synthetic.pgcustom"
                subprocess.run([str(client_bin / "pg_dump"), "--format=custom",
                    "--no-owner", "--no-acl", "--file=" + str(archive),
                    "--dbname=" + self.url], check=True, capture_output=True,
                    timeout=90)
                archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
                self.assertGreater(archive.stat().st_size, 1000)
                subprocess.run([str(client_bin / "pg_restore"), "--no-owner",
                    "--no-acl", "--single-transaction", "--exit-on-error",
                    "--dbname=" + restore_url, str(archive)],
                    check=True, capture_output=True, timeout=120)
                self.assertEqual(snapshot(restore_url), before)
                self.assertIsNone(read(db_url=restore_url))
                # Exercise the restored Core HTTP endpoints, not merely SQL
                # equality: 015 event-key replay and 014 DEAD must be stable.
                # Revoking the *service* bearer blocks terminal replay but
                # does not establish human IdP/GLPI authority.
                with patch.object(base.x, "db",
                                  side_effect=lambda: self.psycopg.connect(restore_url)), \
                     patch.object(main, "db",
                                  side_effect=lambda: self.psycopg.connect(restore_url)), \
                     patch.object(main, "ADMIN", internal):
                    with TestClient(main.app) as restored:
                        restored_source = restored.post(
                            f"/api/runs/{ids['run']}/events", json=bodies[1],
                            headers={"Authorization": "Bearer " + internal})
                        self.assertEqual((
                            restored_source.status_code,
                            restored_source.json()["idempotent"],
                            restored_source.json()["sequence"]), (200, True, 1))
                        restored_dead = restored.post(
                            dead_path, json=dead_body, headers=dead_headers)
                        self.assertEqual((
                            restored_dead.status_code,
                            restored_dead.json()["status"],
                            restored_dead.json()["idempotent"]), (200, "DEAD", True))
                        self.assertEqual(
                            restored_dead.json()["receipt_sha256"], receipt_sha)
                        # Native PG16 restored 014 receipt is independently
                        # readable over canonical Core HTTP without the
                        # pre-restart eighth lease token.
                        recovery_auth = [{
                            "token_sha256": hashlib.sha256(
                                self.token_a.encode()).hexdigest(),
                            "actor_id": "svc-TEN-A", "tenant_ids": ["TEN-A"],
                            "permissions": ["hitl:reject:deliver",
                                            "hitl:reject:terminal",
                                            "hitl:reject:recover"]}]
                        with patch.dict(os.environ, {
                                "AIOPS_XREF_READ_AUTHZ_JSON": json.dumps(recovery_auth)}):
                            token_free = restored.post(
                                dead_path.removesuffix("/dead") +
                                "/terminal-receipt",
                                json={**{k: v for k, v in dead_body.items()
                                       if k != "lease_token"},
                                      "incident_id": ids["inc"]},
                                headers=dead_headers)
                            self.assertEqual((
                                token_free.status_code,
                                token_free.json()["status"],
                                token_free.json()["idempotent"]),
                                (200, "DEAD", True))
                            self.assertEqual(
                                token_free.json()["receipt_sha256"], receipt_sha)
                            self.assertNotIn("lease_token", token_free.text)
                        revoked_auth = [{
                            "token_sha256": hashlib.sha256(
                                self.token_b.encode()).hexdigest(),
                            "actor_id": "svc-TEN-B", "tenant_ids": ["TEN-B"],
                            "permissions": [
                                "hitl:reject:deliver", "hitl:reject:terminal"]}]
                        with patch.dict(os.environ, {
                            "AIOPS_XREF_READ_AUTHZ_JSON": json.dumps(revoked_auth)}):
                            revoked = restored.post(
                                dead_path, json=dead_body, headers=dead_headers)
                            self.assertEqual((
                                revoked.status_code, revoked.json()["status"]),
                                (401, "UNKNOWN"))
                        projected = restored.get(f"/api/runs/{ids['run']}")
                        self.assertEqual(projected.status_code, 200)
                        self.assertEqual(len(projected.json()["events"]), 10)
                self.assertEqual(snapshot(restore_url), before)
        finally:
            if created:
                with self.psycopg.connect(self.admin_url, autocommit=True) as admin:
                    admin.execute(self.sql.SQL("drop database {} with (force)").format(
                        self.sql.Identifier(restore_name)))
        self.assertEqual(snapshot(self.url), before)
        self._no_effect()

        out = os.environ.get("AIOPS_CORE_TERMINAL_RECEIPT_DIR")
        if out:
            target = Path(out)
            if not str(target).startswith("/tmp/core-terminal-"):
                raise RuntimeError("refuse non-disposable receipt path")
            target.mkdir(parents=True, exist_ok=True)
            receipt = {
                "schema": "aiops.core-graph005-terminal-014-015-joined.v1",
                "source_head": os.environ["AIOPS_EXPECTED_HEAD_SHA"],
                "synthetic_only": True, "core_api_writes": 10,
                "source_ids": [e[0] for e in expected],
                "source_physical_sequences": [1, 2, 4, 5, 6, 8, 9],
                "source_ordinals": list(range(1, 8)),
                "core_hash_domains": {
                    "full_event": binding.FULL_DOMAIN,
                    "payload": binding.PAYLOAD_DOMAIN},
                "core_hashes": [{
                    "source_event_id": e["source_event_id"],
                    "full_event_sha256": e["full_event_hash"],
                    "payload_sha256": e["payload_hash"],
                } for e in proof["events"]],
                "fixture_hash_domains_separate": True,
                "source_pre_revocation": "PASS_SYNTHETIC_ONLY",
                "source_post_revocation": "UNKNOWN",
                "negative_actor_source": 9,
                "worker_events": "CORE_WRITTEN_SHAPED_FIXTURE_ONLY",
                "real_worker_os_processes_in_this_test": 0,
                "terminal_014_status": "DEAD", "terminal_attempts": 8,
                "terminal_receipt_sha256": receipt_sha,
                "terminal_replay_idempotent": True,
                "core_event_key_replay_idempotent": True,
                "audit_013_014_immutable": True,
                "migration_chain": ["001", "004", "009", "010", "011", "012",
                                    "013", "014", "015"],
                "migration_015_transaction_rollback": True,
                "migration_015_reapply": True,
                "native_pg16_restore": True,
                "archive_sha256": archive_sha, "archive_retained": False,
                "signed_run_ownership_tamper": "UNKNOWN_NO_MUTATION",
                "restored_http_source_replay": "200_IDEMPOTENT",
                "restored_http_dead_replay": "200_DEAD_IDEMPOTENT",
                "restored_http_token_free_readback": "200_DEAD_IDEMPOTENT",
                "restored_http_service_revocation": "401_UNKNOWN",
                "restored_http_run_event_count": 10,
                "human_idp_actor_authenticated": False,
                "human_glpi_authority": "UNKNOWN",
                "portable_signature": "NONE", "execution_allowed": False,
                "effect_allowed": False, "release_stable": "NO_GO",
                "rollback": "REVERT_CORE_TEST_AND_WORKFLOW_ONLY_KEEP_AUDIT",
            }
            receipt["payload_sha256"] = hashlib.sha256(json.dumps(
                receipt, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            (target / "graph005-terminal-joined.json").write_text(
                json.dumps(receipt, sort_keys=True, indent=2) + "\n")

    def test_terminal_canonical_http_insert_failure_rolls_back_atomically(self):
        ids, digest, tokens = self._exhaust()
        client = self._canonical_core_client()
        path = f"/api/tenants/TEN-A/hitl/reject-delivery/{ids['event']}/dead"
        body = {"owner": "svc-TEN-A", "run_id": ids["run"],
                "proposal_id": ids["proposal"], "proposal_hash": digest,
                "proposal_revision": 1, "lease_token": tokens[-1],
                "execution_allowed": False, "effect_allowed": False}
        headers = {"Authorization": "Bearer " + self.token_a}
        # Simulate a DB insert failure *after* Core's UPDATE, without
        # mutating schema or dropping any immutable audit rows.
        with patch.object(delivery, "_TERMINAL_INSERT_SQL",
                          "insert into aiops.hitl_reject_terminal_receipts "
                          "(no_such_column) values (%s)"):
            failed = client.post(path, json=body, headers=headers)
        self.assertEqual((failed.status_code, failed.json()["status"]),
                         (503, "UNKNOWN"))
        with self.psycopg.connect(self.url) as db:
            self.assertEqual(db.execute(
                "select status,attempts from aiops.hitl_decision_outbox "
                "where event_id=%s", (ids["event"],)).fetchone(), ("LEASED", 8))
            self.assertEqual(db.execute(
                "select count(*) from aiops.hitl_reject_terminal_receipts "
                "where event_id=%s", (ids["event"],)).fetchone()[0], 0)
        recovered = client.post(path, json=body, headers=headers)
        self.assertEqual((recovered.status_code, recovered.json()["status"]),
                         (200, "DEAD"))
        with self.psycopg.connect(self.url) as db:
            self.assertEqual(db.execute(
                "select count(*) from aiops.hitl_reject_terminal_receipts "
                "where event_id=%s", (ids["event"],)).fetchone()[0], 1)
        self._no_effect()


    def test_terminal_restart_recovery_and_token_free_receipt_fail_closed(self):
        """Core HTTP handles an expired eighth lease without exporting its token."""
        ids, digest, tokens = self._exhaust()
        client = self._canonical_core_client()
        root = f"/api/tenants/TEN-A/hitl/reject-delivery/{ids['event']}"
        body = {"owner": "svc-TEN-A", "run_id": ids["run"],
                "incident_id": ids["inc"],
                "proposal_id": ids["proposal"], "proposal_hash": digest,
                "proposal_revision": 1, "execution_allowed": False,
                "effect_allowed": False}
        headers = {"Authorization": "Bearer " + self.token_a}
        entry_a = {"token_sha256": hashlib.sha256(self.token_a.encode()).hexdigest(),
                   "actor_id": "svc-TEN-A", "tenant_ids": ["TEN-A"],
                   "permissions": ["hitl:reject:deliver", "hitl:reject:terminal",
                                   "hitl:reject:recover"]}
        entry_b = {"token_sha256": hashlib.sha256(self.token_b.encode()).hexdigest(),
                   "actor_id": "svc-TEN-B", "tenant_ids": ["TEN-B"],
                   "permissions": ["hitl:reject:deliver", "hitl:reject:terminal",
                                   "hitl:reject:recover"]}
        # No implicit grant to existing terminal callers.
        self.assertEqual(client.post(root + "/terminal-recover", json=body,
                                     headers=headers).status_code, 403)
        with patch.dict(os.environ, {
                "AIOPS_XREF_READ_AUTHZ_JSON": json.dumps([entry_a, entry_b])}):
            self.assertEqual(client.post(root + "/terminal-receipt",
                                         json=body, headers=headers).json()["status"],
                             "UNKNOWN")
            self.assertEqual(client.post(root + "/terminal-recover",
                                         json=body).status_code, 401)
            self.assertEqual(client.post(root + "/terminal-recover",
                json=body, headers={"Authorization": "Bearer " + self.token_b}
            ).status_code, 403)
            for delta in ({"owner": "svc-foreign"}, {"run_id": "RUN-foreign"},
                          {"incident_id": "INC-foreign"},
                          {"proposal_id": "PROPOSAL-foreign"},
                          {"proposal_hash": "0" * 64},
                          {"proposal_revision": 2}, {"effect_allowed": True}):
                denied = client.post(root + "/terminal-recover",
                                     json={**body, **delta}, headers=headers)
                self.assertEqual((denied.status_code, denied.json()["status"]),
                                 (200, "UNKNOWN"))
            foreign = client.post(root.replace("/TEN-A/", "/TEN-B/") +
                "/terminal-recover", json={**body, "owner": "svc-TEN-B"},
                headers={"Authorization": "Bearer " + self.token_b})
            self.assertEqual((foreign.status_code, foreign.json()["status"]),
                             (200, "UNKNOWN"))
            proof_file = Path(self.proof_path)
            proof_file.write_text(json.dumps({
                "schema": "aiops.core-ownership-proof.v1", "proofs": {}}))
            self.assertEqual(client.post(root + "/terminal-recover",
                json=body, headers=headers).json()["status"], "UNKNOWN")
            self._write_proofs()
            first = client.post(root + "/terminal-recover",
                                json=body, headers=headers)
            read = client.post(root + "/terminal-receipt",
                               json=body, headers=headers)
            replay = client.post(root + "/terminal-recover",
                                 json=body, headers=headers)
            self.assertEqual((first.status_code, first.json()["status"],
                              first.json()["idempotent"]), (200, "DEAD", False))
            self.assertEqual((read.status_code, read.json()["status"],
                              read.json()["idempotent"]), (200, "DEAD", True))
            self.assertEqual((replay.status_code, replay.json()["status"],
                              replay.json()["idempotent"]), (200, "DEAD", True))
            receipt_sha = first.json()["receipt_sha256"]
            self.assertEqual(read.json()["receipt_sha256"], receipt_sha)
            self.assertEqual(replay.json()["receipt_sha256"], receipt_sha)
            # This binding comes from the canonical Core Run row, not a
            # Worker-supplied Incident assertion or immutable 014 payload.
            self.assertEqual([r.json().get("incident_id")
                              for r in (first, read, replay)], [ids["inc"]] * 3)
            post_dead_foreign = client.post(root + "/terminal-receipt",
                json={**body, "incident_id": "INC-foreign"}, headers=headers)
            self.assertEqual((post_dead_foreign.status_code,
                              post_dead_foreign.json()["status"]), (200, "UNKNOWN"))
            for response in (first, read, replay):
                self.assertNotIn("lease_token", response.text)
                self.assertNotIn(tokens[-1], response.text)
                self.assertFalse(response.json()["effect_allowed"])
                self.assertFalse(response.json()["execution_allowed"])
            with self.psycopg.connect(self.url) as db:
                self.assertEqual(db.execute(
                    "select status,attempts from aiops.hitl_decision_outbox "
                    "where event_id=%s", (ids["event"],)).fetchone(), ("DEAD", 8))
                self.assertEqual(db.execute(
                    "select count(*) from aiops.hitl_reject_terminal_receipts "
                    "where event_id=%s", (ids["event"],)).fetchone()[0], 1)
            # A revoked service bearer or revoked signed ownership proof
            # cannot read even an already-committed terminal receipt.
            with patch.dict(os.environ, {
                    "AIOPS_XREF_READ_AUTHZ_JSON": json.dumps([entry_b])}):
                self.assertEqual(client.post(root + "/terminal-receipt",
                    json=body, headers=headers).status_code, 401)
            proof_file.write_text(json.dumps({
                "schema": "aiops.core-ownership-proof.v1", "proofs": {}}))
            self.assertEqual(client.post(root + "/terminal-receipt",
                json=body, headers=headers).json()["status"], "UNKNOWN")
            self._write_proofs()
            self.assertEqual(client.post(root + "/terminal-receipt",
                json=body, headers=headers).json()["receipt_sha256"], receipt_sha)
        target = os.environ.get("AIOPS_CORE_TERMINAL_RECEIPT_DIR")
        if target:
            receipt = {"schema": "aiops.core-terminal-restart-recovery-ci.v1",
                       "source_head": os.environ["AIOPS_EXPECTED_HEAD_SHA"],
                       "core_http_recovery": "200_DEAD", "readback": "200_DEAD",
                       "replay_idempotent": True, "audit_014_rows": 1,
                       "attempts": 8, "receipt_sha256": receipt_sha,
                       "wrong_permission": 403, "revoked_bearer": 401,
                       "revoked_source_proof": "UNKNOWN",
                       "lease_token_exported": False,
                       "incident_id_core_readback": True,
                       "post_dead_foreign_incident": "200_UNKNOWN",
                       "real_worker_os_processes": 0,
                       "human_glpi_authority": "UNKNOWN",
                       "execution_allowed": False, "effect_allowed": False,
                       "rollback": "REVERT_CORE_CODE_TEST_WORKFLOW_KEEP_013_014_015"}
            receipt["payload_sha256"] = hashlib.sha256(json.dumps(
                receipt, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            Path(target).mkdir(parents=True, exist_ok=True)
            (Path(target) / "terminal-recovery.json").write_text(
                json.dumps(receipt, sort_keys=True, indent=2) + "\n")
        self._no_effect()

    def test_terminal_rotated_service_credential_restart_fence(self):
        """New bearer for the SAME service actor works; revoked old bearer fails.

        This is a disposable Core auth rotation, NOT a human IdP identity,
        production Worker restart, or independently signed external claim.
        """
        ids, digest, tokens = self._exhaust()
        client = self._canonical_core_client()
        path = (f"/api/tenants/TEN-A/hitl/reject-delivery/"
                f"{ids['event']}")
        body = {"owner": "svc-TEN-A", "run_id": ids["run"],
                "incident_id": ids["inc"],
                "proposal_id": ids["proposal"], "proposal_hash": digest,
                "proposal_revision": 1, "execution_allowed": False,
                "effect_allowed": False}
        old = {"Authorization": "Bearer " + self.token_a}
        rotated_token = "ci-core-rotated-service-" + "R" * 40
        new = {"Authorization": "Bearer " + rotated_token}
        rotated_entry = {
            "token_sha256": hashlib.sha256(rotated_token.encode()).hexdigest(),
            "actor_id": "svc-TEN-A", "tenant_ids": ["TEN-A"],
            "permissions": ["hitl:reject:deliver", "hitl:reject:terminal",
                            "hitl:reject:recover"]}
        with patch.dict(os.environ, {
                "AIOPS_XREF_READ_AUTHZ_JSON": json.dumps([rotated_entry])}):
            # Rotation revokes the old bearer even though the owner string
            # remains identical; no eighth lease token is supplied.
            self.assertEqual(client.post(path + "/terminal-recover",
                json=body, headers=old).status_code, 401)
            self.assertEqual(client.post(path + "/terminal-receipt",
                json=body, headers=new).json()["status"], "UNKNOWN")
            recovered = client.post(path + "/terminal-recover",
                                    json=body, headers=new)
            self.assertEqual((recovered.status_code, recovered.json()["status"],
                              recovered.json()["idempotent"]),
                             (200, "DEAD", False))
            readback = client.post(path + "/terminal-receipt",
                                   json=body, headers=new)
            self.assertEqual((readback.status_code, readback.json()["status"],
                              readback.json()["idempotent"]),
                             (200, "DEAD", True))
            self.assertEqual(readback.json()["receipt_sha256"],
                             recovered.json()["receipt_sha256"])
            self.assertEqual(client.post(path + "/terminal-receipt",
                json=body, headers=old).status_code, 401)
            self.assertNotIn("lease_token", recovered.text)
            self.assertNotIn(tokens[-1], recovered.text)
            self.assertNotIn(rotated_token, recovered.text)
        # Revoke the rotated bearer as well: immutable audit remains in PG16,
        # but the endpoint must not expose it to a no-longer-authorized actor.
        with patch.dict(os.environ, {
                "AIOPS_XREF_READ_AUTHZ_JSON": json.dumps([{
                    "token_sha256": hashlib.sha256(self.token_b.encode()).hexdigest(),
                    "actor_id": "svc-TEN-B", "tenant_ids": ["TEN-B"],
                    "permissions": ["hitl:reject:deliver", "hitl:reject:terminal",
                                    "hitl:reject:recover"]}])}):
            self.assertEqual(client.post(path + "/terminal-receipt",
                json=body, headers=new).status_code, 401)
        with self.psycopg.connect(self.url) as db:
            self.assertEqual(db.execute(
                "select status,attempts from aiops.hitl_decision_outbox "
                "where event_id=%s", (ids["event"],)).fetchone(), ("DEAD", 8))
            self.assertEqual(db.execute(
                "select count(*) from aiops.hitl_reject_terminal_receipts "
                "where event_id=%s", (ids["event"],)).fetchone()[0], 1)
        target = os.environ.get("AIOPS_CORE_TERMINAL_RECEIPT_DIR")
        if target:
            receipt = {
                "schema": "aiops.core-terminal-credential-rotation-ci.v1",
                "source_head": os.environ["AIOPS_EXPECTED_HEAD_SHA"],
                "old_bearer_revoked": 401, "rotated_bearer_recovered": "200_DEAD",
                "rotated_bearer_readback": "200_DEAD_IDEMPOTENT",
                "rotated_bearer_revoked": 401, "attempts": 8,
                "audit_014_rows": 1, "lease_token_exported": False,
                "real_worker_os_processes": 0, "human_glpi_authority": "UNKNOWN",
                "execution_allowed": False, "effect_allowed": False,
                "rollback": "REVERT_CORE_TEST_WORKFLOW_KEEP_013_014_015"}
            receipt["payload_sha256"] = hashlib.sha256(json.dumps(
                receipt, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            Path(target).mkdir(parents=True, exist_ok=True)
            (Path(target) / "credential-rotation.json").write_text(
                json.dumps(receipt, sort_keys=True, indent=2) + "\n")
        self._no_effect()

    def test_terminal_same_tenant_foreign_actor_cannot_steal_rotated_lease(self):
        """A new bearer is not a new lease owner, even inside the same tenant.

        This is a Core-only HTTP/PG16 contract for Policy's separately
        registered Worker activity; no actual Worker or Temporal process runs.
        """
        ids, digest, tokens = self._exhaust()
        client = self._canonical_core_client()
        root = f"/api/tenants/TEN-A/hitl/reject-delivery/{ids['event']}"
        body = {"owner": "svc-TEN-A", "run_id": ids["run"],
                "incident_id": ids["inc"], "proposal_id": ids["proposal"],
                "proposal_hash": digest, "proposal_revision": 1,
                "execution_allowed": False, "effect_allowed": False}
        outsider_token = "ci-core-same-tenant-foreign-" + "F" * 40
        rotated_token = "ci-core-same-actor-rotation-" + "R" * 40
        def entry(token, actor):
            return {"token_sha256": hashlib.sha256(token.encode()).hexdigest(),
                    "actor_id": actor, "tenant_ids": ["TEN-A"],
                    "permissions": ["hitl:reject:deliver",
                                    "hitl:reject:terminal", "hitl:reject:recover"]}
        outsider = {"Authorization": "Bearer " + outsider_token}
        rotated = {"Authorization": "Bearer " + rotated_token}
        old = {"Authorization": "Bearer " + self.token_a}
        with patch.dict(os.environ, {"AIOPS_XREF_READ_AUTHZ_JSON": json.dumps([
                entry(outsider_token, "svc-TEN-A-foreign"),
                entry(rotated_token, "svc-TEN-A")])}):
            self.assertEqual(client.post(root + "/terminal-recover",
                json={**body, "owner": "svc-TEN-A-foreign"},
                headers=outsider).json()["status"], "UNKNOWN")
            self.assertEqual(client.post(root + "/terminal-recover",
                json=body, headers=outsider).json()["status"], "UNKNOWN")
            self.assertEqual(client.post(root + "/terminal-receipt",
                json={**body, "owner": "svc-TEN-A-foreign"},
                headers=outsider).json()["status"], "UNKNOWN")
            self.assertEqual(client.post(root + "/terminal-recover",
                json=body, headers=old).status_code, 401)
            with self.psycopg.connect(self.url) as db:
                self.assertEqual(db.execute(
                    "select status,attempts from aiops.hitl_decision_outbox "
                    "where event_id=%s", (ids["event"],)).fetchone(),
                    ("LEASED", 8))
                self.assertEqual(db.execute(
                    "select count(*) from aiops.hitl_reject_terminal_receipts "
                    "where event_id=%s", (ids["event"],)).fetchone()[0], 0)
            recovered = client.post(root + "/terminal-recover",
                                    json=body, headers=rotated)
            readback = client.post(root + "/terminal-receipt",
                                   json=body, headers=rotated)
            self.assertEqual((recovered.status_code, recovered.json()["status"],
                              recovered.json()["idempotent"]),
                             (200, "DEAD", False))
            self.assertEqual((readback.status_code, readback.json()["status"],
                              readback.json()["idempotent"]),
                             (200, "DEAD", True))
            self.assertEqual(recovered.json()["receipt_sha256"],
                             readback.json()["receipt_sha256"])
            self.assertEqual(client.post(root + "/terminal-receipt",
                json={**body, "owner": "svc-TEN-A-foreign"},
                headers=outsider).json()["status"], "UNKNOWN")
            self.assertNotIn(tokens[-1], recovered.text)
            self.assertNotIn(rotated_token, recovered.text)
        with patch.dict(os.environ, {"AIOPS_XREF_READ_AUTHZ_JSON":
                json.dumps([entry(outsider_token, "svc-TEN-A-foreign")])}):
            self.assertEqual(client.post(root + "/terminal-receipt",
                json=body, headers=rotated).status_code, 401)
        with self.psycopg.connect(self.url) as db:
            self.assertEqual(db.execute(
                "select status,attempts from aiops.hitl_decision_outbox "
                "where event_id=%s", (ids["event"],)).fetchone(), ("DEAD", 8))
            self.assertEqual(db.execute(
                "select count(*) from aiops.hitl_reject_terminal_receipts "
                "where event_id=%s", (ids["event"],)).fetchone()[0], 1)
        target = os.environ.get("AIOPS_CORE_TERMINAL_RECEIPT_DIR")
        if target:
            receipt = {
                "schema": "aiops.core-terminal-lease-owner-fence-ci.v1",
                "source_head": os.environ["AIOPS_EXPECTED_HEAD_SHA"],
                "same_tenant_foreign_actor": "200_UNKNOWN_NO_MUTATION",
                "foreign_owner_claim": "200_UNKNOWN_NO_MUTATION",
                "old_bearer_revoked": 401,
                "same_actor_rotated_bearer": "200_DEAD",
                "readback": "200_DEAD_IDEMPOTENT",
                "postcommit_foreign_actor": "200_UNKNOWN",
                "rotated_bearer_revoked": 401,
                "audit_014_rows": 1, "attempts": 8,
                "receipt_sha256": readback.json()["receipt_sha256"],
                "lease_token_exported": False,
                "real_worker_os_processes": 0,
                "human_glpi_authority": "UNKNOWN",
                "execution_allowed": False, "effect_allowed": False,
                "rollback": "REVERT_CORE_TEST_WORKFLOW_KEEP_013_014_015"}
            receipt["payload_sha256"] = hashlib.sha256(json.dumps(
                receipt, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            Path(target).mkdir(parents=True, exist_ok=True)
            (Path(target) / "lease-owner-fence.json").write_text(
                json.dumps(receipt, sort_keys=True, indent=2) + "\n")
        self._no_effect()

    def test_terminal_restart_recovery_insert_rollback_and_concurrency(self):
        ids, digest, tokens = self._exhaust()
        body = {"owner": "svc-TEN-A", "run_id": ids["run"],
                "incident_id": ids["inc"],
                "proposal_id": ids["proposal"], "proposal_hash": digest,
                "proposal_revision": 1, "execution_allowed": False,
                "effect_allowed": False}
        entry = {"token_sha256": hashlib.sha256(self.token_a.encode()).hexdigest(),
                 "actor_id": "svc-TEN-A", "tenant_ids": ["TEN-A"],
                 "permissions": ["hitl:reject:deliver", "hitl:reject:terminal",
                                 "hitl:reject:recover"]}
        with patch.dict(os.environ, {
                "AIOPS_XREF_READ_AUTHZ_JSON": json.dumps([entry])}):
            # Neither the seventh attempt nor an unexpired eighth lease
            # may be promoted to DEAD by token-free recovery.
            with self.psycopg.connect(self.url) as db:
                db.execute("update aiops.hitl_decision_outbox "
                           "set attempts=7 where event_id=%s", (ids["event"],))
            early = delivery.terminal_recover(
                "TEN-A", ids["event"], body,
                authorization="Bearer " + self.token_a)
            self.assertEqual(json.loads(early.body)["status"], "UNKNOWN")
            with self.psycopg.connect(self.url) as db:
                db.execute("update aiops.hitl_decision_outbox "
                           "set attempts=8,lease_until=now()+interval '30 seconds' "
                           "where event_id=%s", (ids["event"],))
            unexpired = delivery.terminal_recover(
                "TEN-A", ids["event"], body,
                authorization="Bearer " + self.token_a)
            self.assertEqual(json.loads(unexpired.body)["status"], "UNKNOWN")
            with self.psycopg.connect(self.url) as db:
                db.execute("update aiops.hitl_decision_outbox "
                           "set lease_until=now()-interval '2 seconds' "
                           "where event_id=%s", (ids["event"],))
            with patch.object(delivery, "_TERMINAL_INSERT_SQL",
                              "insert into aiops.hitl_reject_terminal_receipts "
                              "(no_such_column) values (%s)"):
                failed = delivery.terminal_recover(
                    "TEN-A", ids["event"], body,
                    authorization="Bearer " + self.token_a)
            self.assertEqual((failed.status_code, json.loads(failed.body)["status"]),
                             (503, "UNKNOWN"))
            with self.psycopg.connect(self.url) as db:
                self.assertEqual(db.execute(
                    "select status,attempts from aiops.hitl_decision_outbox "
                    "where event_id=%s", (ids["event"],)).fetchone(), ("LEASED", 8))
                self.assertEqual(db.execute(
                    "select count(*) from aiops.hitl_reject_terminal_receipts "
                    "where event_id=%s", (ids["event"],)).fetchone()[0], 0)
            barrier = threading.Barrier(2)
            def contender():
                barrier.wait(timeout=10)
                response = delivery.terminal_recover(
                    "TEN-A", ids["event"], body,
                    authorization="Bearer " + self.token_a)
                return response.status_code, json.loads(response.body)
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(contender) for _ in range(2)]
                results = [f.result(timeout=20) for f in futures]
            self.assertEqual(sorted((r[0], r[1]["status"], r[1]["idempotent"])
                                    for r in results),
                             [(200, "DEAD", False), (200, "DEAD", True)])
            self.assertEqual(len({r[1]["receipt_sha256"] for r in results}), 1)
            with self.psycopg.connect(self.url) as db:
                self.assertEqual(db.execute(
                    "select count(*) from aiops.hitl_reject_terminal_receipts "
                    "where event_id=%s", (ids["event"],)).fetchone()[0], 1)
        self._no_effect()
