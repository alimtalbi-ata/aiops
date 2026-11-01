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

