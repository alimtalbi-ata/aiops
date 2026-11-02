"""Candidate-only PostgreSQL 16 HITL outbox SQL failure injection.

TEST HARNESS ONLY: SQL claim/ACK below is a model, NOT Core API or Worker delivery.
No real human approval, Temporal signal, executor, GLPI, LIVE, or effect receipt.
Run only inside the dedicated disposable GitHub Actions PostgreSQL service.
"""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import unittest
import uuid
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ("001_schema.sql", "004_operational_model.sql",
              "009_ai_decision_ledger.sql", "010_evidence_identity.sql",
              "011_hitl_decision_outbox.sql", "012_itsm_xref_read.sql")
PINNED = {"009_ai_decision_ledger.sql": "bfed91982654b6baf0026408fa5134a22af421bb",
          "010_evidence_identity.sql": "1ddafd94639af60ce38b6df0acafd7f63d6b4af2",
          "011_hitl_decision_outbox.sql": "b096af57cb19b9618e3d7d4d68a8ef3d56890934",
          "012_itsm_xref_read.sql": "9408dcf9d92d5bfbdb75968a5a0b0a55f2985457"}


def _blob_sha(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


class CandidateOutboxPG16(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("AIOPS_CI_OUTBOX_DISPOSABLE") != "YES":
            raise RuntimeError("refuse_non_disposable_hitl_test")
        import psycopg
        from psycopg import sql
        cls.psycopg, cls.sql = psycopg, sql
        parsed = urlsplit(os.environ["DATABASE_URL"])
        if (parsed.scheme != "postgresql" or parsed.hostname != "postgres"
                or parsed.port != 5432 or parsed.path != "/aiops"
                or parsed.username != "aiops" or parsed.query or parsed.fragment):
            raise RuntimeError("refuse_non_ci_postgres_target")
        cls.admin_url = os.environ["DATABASE_URL"]
        cls.database = "aiops_hitl_pg16_ci"
        cls.url = urlunsplit((parsed.scheme, parsed.netloc, "/" + cls.database, "", ""))
        for name, expected in PINNED.items():
            raw = (ROOT / "db/migrations" / name).read_bytes()
            if _blob_sha(raw) != expected:
                raise RuntimeError("migration_blob_mismatch:" + name)
        with psycopg.connect(cls.admin_url, autocommit=True) as admin:
            v = int(admin.execute("show server_version_num").fetchone()[0])
            if not 160000 <= v < 170000:
                raise RuntimeError("requires_postgresql_16")
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(cls.database)))
        try:
            with psycopg.connect(cls.url) as db:
                for name in MIGRATIONS:
                    db.execute((ROOT / "db/migrations" / name).read_text())
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        if not hasattr(cls, "database"):
            return
        with cls.psycopg.connect(cls.admin_url, autocommit=True) as admin:
            admin.execute(cls.sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                cls.sql.Identifier(cls.database)))

    def _fixture(self):
        """REJECT notification only. Actor is explicitly UNVERIFIED, never a human approval."""
        suffix = uuid.uuid4().hex
        run, analysis, critique = ("CI-HITL-RUN-" + suffix, "CI-HITL-AN-" + suffix,
                                   "CI-HITL-CR-" + suffix)
        proposal, approval, event = ("CI-HITL-ACT-" + suffix, "CI-HITL-APR-" + suffix,
                                     "CI-HITL-HDO-" + suffix)
        evidence = "CI-HITL-EVD-" + suffix
        digest = hashlib.sha256(("SYNTHETIC_UNVERIFIED:" + suffix).encode()).hexdigest()
        evidence_ids = json.dumps([evidence])
        action = {"action_id": "CI-FIXTURE", "risk_tier": "LOW",
                  "target_ci_id": "CI-SYNTHETIC", "advisory_only": True,
                  "requires_human_approval": True}
        with self.psycopg.connect(self.url) as c:
            c.execute("insert into aiops.runs(run_id,mode,scenario_id,status,idempotency_key) "
                      "values(%s,'DEMO','CI-HITL','CREATED',%s)", (run, "ci-run-" + suffix))
            c.execute("insert into aiops.evidence "
                      "(evidence_id,source,claim,confidence,provenance,payload_hash,payload) "
                      "values(%s,'ci-fixture','synthetic outbox qualification',0.5,"
                      "'{\"synthetic\":true}',%s,'{}')", (evidence, digest))
            c.execute("insert into aiops.analysis_records "
                      "(analysis_id,run_id,idempotency_key,revision,contract_version,provider,"
                      "model,prompt_version,evidence_ids,evidence_set_hash,output,confidence,status) "
                      "values(%s,%s,%s,1,'ci','ci-fixture','none','ci',%s,%s,%s,0.5,'VALID')",
                      (analysis, run, "ci-analysis-" + suffix, evidence_ids, digest,
                       json.dumps({"recommended_actions": [action]})))
            c.execute("insert into aiops.critique_records "
                      "(critique_id,idempotency_key,analysis_id,run_id,contract_version,"
                      "provider,model,validated,evidence_ids,output,diagnostic_confidence) "
                      "values(%s,%s,%s,%s,'ci','ci-fixture','none',true,%s,%s,0.5)",
                      (critique, "ci-critique-" + suffix, analysis, run, evidence_ids,
                       json.dumps({"issues": [], "unsafe_actions": []})))
            c.execute("insert into aiops.action_proposals "
                      "(proposal_id,run_id,analysis_id,critique_id,source_action_id,"
                      "proposal_revision,target_ci_id,action_type,risk_tier,evidence_ids,"
                      "preconditions,expected_postconditions,proposal_hash,status,expires_at) "
                      "values(%s,%s,%s,%s,'CI-FIXTURE',1,'CI-SYNTHETIC',"
                      "'COLLECT_DIAGNOSTICS','LOW',%s,'[\"ci precondition\"]',"
                      "'[\"ci postcondition\"]',%s,'PROPOSED',now()+interval '1 hour')",
                      (proposal, run, analysis, critique, evidence_ids, digest))
            c.execute("insert into aiops.approval_records "
                      "(approval_id,proposal_id,proposal_hash,actor_id,actor_role,decision,"
                      "nonce,expires_at,audit) values(%s,%s,%s,'SYNTHETIC_UNVERIFIED',"
                      "'ci_fixture','REJECT',%s,now()+interval '1 hour',%s)",
                      (approval, proposal, digest, "ci-nonce-" + suffix,
                       json.dumps({"synthetic": True, "identity_attested": False})))
            c.execute("update aiops.action_proposals set status='REJECTED' where proposal_id=%s",
                      (proposal,))
            c.execute("insert into aiops.hitl_decision_outbox "
                      "(event_id,proposal_id,run_id,proposal_hash,proposal_revision,"
                      "decision,source_status,approval_id) "
                      "values(%s,%s,%s,%s,1,'REJECT','REJECTED',%s)",
                      (event, proposal, run, digest, approval))
        return event, proposal

    def _claim_sql_model(self, event, owner):
        """Test-only SQL model of SKIP LOCKED; NOT the Core claim endpoint."""
        token = uuid.uuid4().hex
        with self.psycopg.connect(self.url) as c:
            return c.execute("""
                with ready as (
                    select event_id from aiops.hitl_decision_outbox
                    where event_id=%s and attempts<20 and available_at<=now()
                      and (status='PENDING' or (status='LEASED' and lease_until<=now()))
                    for update skip locked
                )
                update aiops.hitl_decision_outbox o
                   set status='LEASED', attempts=o.attempts+1,
                       lease_owner=%s, lease_token=%s,
                       lease_until=now()+interval '15 seconds'
                  from ready where o.event_id=ready.event_id
                returning o.event_id,o.attempts
            """, (event, owner, token)).fetchall(), token

    def _ack_sql_model(self, event, token):
        """Simulate committed ACK and digest replay; NOT a Core HTTP ACK."""
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.psycopg.connect(self.url) as c:
            row = c.execute("select status,lease_token,lease_until "
                            "from aiops.hitl_decision_outbox where event_id=%s for update",
                            (event,)).fetchone()
            if row[0] == "DELIVERED":
                return (row[1] == digest, row[1] == digest)
            if row[0] != "LEASED" or row[1] != token or not row[2]:
                return False, False
            if not c.execute("select %s > now()", (row[2],)).fetchone()[0]:
                return False, False
            c.execute("update aiops.hitl_decision_outbox "
                      "set status='DELIVERED',lease_token=%s,delivered_at=now() "
                      "where event_id=%s", (digest, event))
            return True, False

    def _no_effect(self):
        with self.psycopg.connect(self.url) as c:
            self.assertEqual(c.execute("select count(*) from aiops.effect_receipts").fetchone()[0], 0)
            self.assertEqual(c.execute("select count(*) from aiops.hitl_decision_outbox "
                                       "where decision='APPROVE'").fetchone()[0], 0)

    def test_concurrent_claim_one_winner(self):
        event, _ = self._fixture()
        barrier = threading.Barrier(2)
        def contender(i):
            barrier.wait(timeout=10)
            return self._claim_sql_model(event, "ci-" + str(i))
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = [f.result(timeout=15) for f in
                        [pool.submit(contender, i) for i in (1, 2)]]
        winners = [(rows, token) for rows, token in outcomes if rows]
        self.assertEqual(len(winners), 1)
        self.assertEqual(winners[0][0], [(event, 1)])
        self.assertEqual(self._ack_sql_model(event, winners[0][1]), (True, False))
        self._no_effect()

    def test_delayed_lease_expiry_and_stale_token(self):
        event, _ = self._fixture()
        with self.psycopg.connect(self.url) as c:
            c.execute("update aiops.hitl_decision_outbox "
                      "set available_at=now()+interval '1 hour' where event_id=%s", (event,))
        self.assertEqual(self._claim_sql_model(event, "early")[0], [])
        with self.psycopg.connect(self.url) as c:
            c.execute("update aiops.hitl_decision_outbox set available_at=now() "
                      "where event_id=%s", (event,))
        first, old_token = self._claim_sql_model(event, "old")
        self.assertEqual(first, [(event, 1)])
        with self.psycopg.connect(self.url) as c:
            c.execute("update aiops.hitl_decision_outbox "
                      "set lease_until=now()-interval '1 second' where event_id=%s", (event,))
        second, new_token = self._claim_sql_model(event, "new")
        self.assertEqual(second, [(event, 2)])
        self.assertEqual(self._ack_sql_model(event, old_token), (False, False))
        self.assertEqual(self._ack_sql_model(event, new_token), (True, False))
        self.assertEqual(self._ack_sql_model(event, new_token), (True, True))
        self._no_effect()

    def test_lost_ack_response_after_commit_duplicate(self):
        event, _ = self._fixture()
        claimed, token = self._claim_sql_model(event, "lost-ack")
        self.assertEqual(claimed, [(event, 1)])
        self.assertEqual(self._ack_sql_model(event, token), (True, False))
        # Response discarded, but the committed row cannot be delivered again.
        self.assertEqual(self._claim_sql_model(event, "retry")[0], [])
        self.assertEqual(self._ack_sql_model(event, token), (True, True))
        self.assertEqual(self._ack_sql_model(event, "forged"), (False, False))
        self._no_effect()

    def test_retry_budget_dead_letter_isolation(self):
        dead, _ = self._fixture()
        healthy, _ = self._fixture()
        with self.psycopg.connect(self.url) as c:
            c.execute("update aiops.hitl_decision_outbox set attempts=19 "
                      "where event_id=%s", (dead,))
        claimed, _ = self._claim_sql_model(dead, "last-retry")
        self.assertEqual(claimed, [(dead, 20)])
        with self.psycopg.connect(self.url) as c:
            c.execute("update aiops.hitl_decision_outbox "
                      "set lease_until=now()-interval '1 second' where event_id=%s", (dead,))
            c.execute("update aiops.hitl_decision_outbox set status='DEAD' "
                      "where event_id=%s and attempts>=20 and lease_until<=now()", (dead,))
        self.assertEqual(self._claim_sql_model(dead, "exhausted")[0], [])
        rows, token = self._claim_sql_model(healthy, "healthy")
        self.assertEqual(rows, [(healthy, 1)])
        self.assertEqual(self._ack_sql_model(healthy, token), (True, False))
        self._no_effect()

    def test_z_pg16_dump_restore_roundtrip(self):
        for client in ("pg_dump", "pg_restore"):
            result = subprocess.run([client, "--version"], capture_output=True, text=True, check=True)
            self.assertRegex(result.stdout, r"\b16\.[0-9]+\b")
        output = os.environ.get("HITL_DR_ARTIFACT")
        if not output or not output.startswith("/tmp/"):
            raise RuntimeError("refuse_non_ci_dr_path")
        subprocess.run(["pg_dump", "--format=custom", "--no-owner", "--no-privileges",
                        "--schema=aiops", "--file=" + output, "--dbname=" + self.url], check=True)
        restore_name = "aiops_hitl_dr_ci"
        parsed = urlsplit(self.admin_url)
        restore_url = urlunsplit((parsed.scheme, parsed.netloc, "/" + restore_name, "", ""))
        with self.psycopg.connect(self.admin_url, autocommit=True) as admin:
            admin.execute(self.sql.SQL("CREATE DATABASE {}").format(self.sql.Identifier(restore_name)))
        try:
            subprocess.run(["pg_restore", "--exit-on-error", "--no-owner", "--no-privileges",
                            "--dbname=" + restore_url, output], check=True)
            with self.psycopg.connect(self.url) as original, self.psycopg.connect(restore_url) as restored:
                for table in ("runs", "action_proposals", "approval_records",
                              "hitl_decision_outbox", "effect_receipts"):
                    a = original.execute("select count(*) from aiops." + table).fetchone()[0]
                    b = restored.execute("select count(*) from aiops." + table).fetchone()[0]
                    self.assertEqual(a, b, table)
                self.assertEqual(restored.execute(
                    "select count(*) from aiops.effect_receipts").fetchone()[0], 0)
        finally:
            with self.psycopg.connect(self.admin_url, autocommit=True) as admin:
                admin.execute(self.sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                    self.sql.Identifier(restore_name)))


if __name__ == "__main__":
    unittest.main()
