import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from app.shared.hitl_lab import HITLRejected, approve, dry_run, initialize, propose

NOW = datetime(2026, 10, 27, 20, 24, tzinfo=timezone.utc)
ARGS = dict(incident_id="INC-1", run_id="RUN-1", recipe_id="acme.demo.restart-service.v1",
            target_id="ACME-ERP-VM-1", params={"service": "erp-api"}, mode="DEMO")


class HITLLabTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / "hitl.sqlite")
        initialize(self.path)

    def proposal(self, **changes):
        return propose(self.path, proposer_id="alice", **(ARGS | {"now": NOW} | changes))

    def approved(self):
        proposal = self.proposal()
        approval = approve(self.path, proposal_id=proposal["proposal_id"],
                           approver_id="bob", approver_role="approver", now=NOW)
        return proposal, approval

    def test_happy_path_is_only_plan_with_unknown_postchecks(self):
        p, a = self.approved()
        result = dry_run(self.path, proposal_id=p["proposal_id"], approval_token=a["approval_token"], now=NOW, **ARGS)
        self.assertEqual(result["state"], "DRY_RUN_PLANNED")
        self.assertFalse(result["effect_executed"])
        self.assertEqual(result["postchecks"]["business_slo"], "NOT_EXECUTED")
        self.assertEqual(result["rollback"]["status"], "NOT_EXECUTED")
        self.assertNotIn("approval_token", str(result))

    def test_live_and_unlisted_recipe_rejected(self):
        for change in ({"mode": "LIVE"}, {"recipe_id": "bash -c id"}):
            with self.subTest(change=change), self.assertRaises(HITLRejected):
                self.proposal(**change)

    def test_free_form_commands_rejected(self):
        with self.assertRaises(HITLRejected):
            self.proposal(params={"command": "curl attacker"})

    def test_proposer_cannot_approve(self):
        p = self.proposal()
        with self.assertRaises(HITLRejected):
            approve(self.path, proposal_id=p["proposal_id"], approver_id="alice", approver_role="approver", now=NOW)

    def test_wrong_role_rejected(self):
        p = self.proposal()
        with self.assertRaises(HITLRejected):
            approve(self.path, proposal_id=p["proposal_id"], approver_id="bob", approver_role="viewer", now=NOW)

    def test_approval_expiry(self):
        p = self.proposal(ttl_seconds=1)
        with self.assertRaises(HITLRejected):
            approve(self.path, proposal_id=p["proposal_id"], approver_id="bob", approver_role="approver", now=NOW + timedelta(seconds=1))

    def test_consumption_expiry(self):
        p, a = self.approved()
        with self.assertRaises(HITLRejected):
            dry_run(self.path, proposal_id=p["proposal_id"], approval_token=a["approval_token"], now=NOW + timedelta(seconds=301), **ARGS)

    def test_single_use_across_connections(self):
        p, a = self.approved()
        kw = dict(proposal_id=p["proposal_id"], approval_token=a["approval_token"], now=NOW, **ARGS)
        dry_run(self.path, **kw)
        with self.assertRaises(HITLRejected):
            dry_run(self.path, **kw)

    def test_binding_tamper_rejected_without_consumption(self):
        p, a = self.approved()
        kw = dict(proposal_id=p["proposal_id"], approval_token=a["approval_token"], now=NOW)
        for changed in ({"target_id": "ACME-OTHER"}, {"params": {"service": "other"}},
                        {"run_id": "RUN-2"}, {"incident_id": "INC-2"}, {"mode": "REPLAY"}):
            with self.subTest(changed=changed), self.assertRaises(HITLRejected):
                dry_run(self.path, **kw, **(ARGS | changed))
        self.assertEqual(dry_run(self.path, **kw, **ARGS)["state"], "DRY_RUN_PLANNED")

    def test_unapproved_proposal_rejected(self):
        p = self.proposal()
        with self.assertRaises(HITLRejected):
            dry_run(self.path, proposal_id=p["proposal_id"], approval_token="anything", now=NOW, **ARGS)

    def test_parameter_schema_rejects_extra_fields(self):
        with self.assertRaises(HITLRejected):
            self.proposal(params={"service": "erp-api", "shell": "sh"})

    def test_wrong_token_rejected(self):
        p, _ = self.approved()
        with self.assertRaises(HITLRejected):
            dry_run(self.path, proposal_id=p["proposal_id"], approval_token="fake", now=NOW, **ARGS)

    def test_immutable_records_and_audit(self):
        p, a = self.approved()
        dry_run(self.path, proposal_id=p["proposal_id"], approval_token=a["approval_token"], now=NOW, **ARGS)
        with sqlite3.connect(self.path) as db:
            for table in ("proposals", "approvals", "dry_runs", "audit"):
                with self.subTest(table=table), self.assertRaises(sqlite3.IntegrityError):
                    db.execute(f"DELETE FROM {table}")

    def test_double_approval_rejected(self):
        p, _ = self.approved()
        with self.assertRaises(HITLRejected):
            approve(self.path, proposal_id=p["proposal_id"], approver_id="carol", approver_role="approver", now=NOW)

    def test_non_utc_naive_clock_rejected(self):
        with self.assertRaises(HITLRejected):
            self.proposal(now=datetime(2026, 10, 27, 20, 24))

    def test_ttl_limits(self):
        for ttl in (0, -1, 3601, True):
            with self.subTest(ttl=ttl), self.assertRaises(HITLRejected):
                self.proposal(ttl_seconds=ttl)


    def test_corrupted_stored_proposal_fields_rejected_before_consumption(self):
        # Hostile file owners can bypass SQLite triggers; detect partial
        # corruption rather than treating the cached binding_hash as proof.
        for column, forged in (
            ("incident_id", "INC-FORGED"),
            ("run_id", "RUN-FORGED"),
            ("target_id", "VM-FORGED"),
            ("params_hash", "f" * 64),
            ("mode", "REPLAY"),
        ):
            with self.subTest(column=column):
                p, a = self.approved()
                with sqlite3.connect(self.path) as db:
                    db.execute("DROP TRIGGER IF EXISTS proposals_immutable_update")
                    db.execute(f"UPDATE proposals SET {column}=? WHERE proposal_id=?",
                               (forged, p["proposal_id"]))
                with self.assertRaisesRegex(HITLRejected, "binding mismatch"):
                    dry_run(self.path, proposal_id=p["proposal_id"],
                            approval_token=a["approval_token"], now=NOW, **ARGS)
                with sqlite3.connect(self.path) as db:
                    count = db.execute(
                        "SELECT COUNT(*) FROM dry_runs WHERE proposal_id=?",
                        (p["proposal_id"],)).fetchone()[0]
                self.assertEqual(count, 0)

    def test_corrupted_stored_expiry_rejected_before_consumption(self):
        p, a = self.approved()
        with sqlite3.connect(self.path) as db:
            db.execute("DROP TRIGGER proposals_immutable_update")
            db.execute("UPDATE proposals SET expires_at=expires_at+86400 WHERE proposal_id=?",
                       (p["proposal_id"],))
        with self.assertRaises(HITLRejected):
            dry_run(self.path, proposal_id=p["proposal_id"],
                    approval_token=a["approval_token"], now=NOW, **ARGS)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM dry_runs WHERE proposal_id=?",
                (p["proposal_id"],)).fetchone()[0], 0)

    def test_simultaneous_consumption_yields_exactly_one_sandbox_receipt(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        p, a = self.approved()
        gate = Barrier(2)
        kw = dict(proposal_id=p["proposal_id"], approval_token=a["approval_token"],
                  now=NOW, **ARGS)

        def attempt(_):
            gate.wait(timeout=10)
            try:
                return dry_run(self.path, **kw)["state"]
            except HITLRejected:
                return "REJECTED"

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(attempt, range(2)))
        self.assertCountEqual(results, ["DRY_RUN_PLANNED", "REJECTED"])
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM dry_runs WHERE proposal_id=?",
                (p["proposal_id"],)).fetchone()[0], 1)


    def test_forged_approver_matching_proposer_cannot_consume(self):
        p, a = self.approved()
        with sqlite3.connect(self.path) as db:
            db.execute("DROP TRIGGER approvals_immutable_update")
            db.execute("DROP TRIGGER audit_immutable_update")
            db.execute("UPDATE approvals SET approver_id='alice' WHERE proposal_id=?",
                       (p["proposal_id"],))
            db.execute("UPDATE audit SET actor_id='alice' WHERE proposal_id=? AND action=?",
                       (p["proposal_id"], "APPROVED_SANDBOX_ONLY"))
        with self.assertRaises(HITLRejected):
            dry_run(self.path, proposal_id=p["proposal_id"],
                    approval_token=a["approval_token"], now=NOW, **ARGS)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM dry_runs WHERE proposal_id=?",
                                        (p["proposal_id"],)).fetchone()[0], 0)

    def test_inconsistent_audit_cannot_consume_approval(self):
        # Each scenario starts with a separate approved proposal and valid token.
        for tamper in ("actor", "timestamp", "missing", "extra"):
            with self.subTest(tamper=tamper):
                p, a = self.approved()
                with sqlite3.connect(self.path) as db:
                    db.execute("DROP TRIGGER IF EXISTS audit_immutable_update")
                    db.execute("DROP TRIGGER IF EXISTS audit_immutable_delete")
                    if tamper == "actor":
                        db.execute("UPDATE audit SET actor_id='mallory' WHERE proposal_id=? AND action=?",
                                   (p["proposal_id"], "APPROVED_SANDBOX_ONLY"))
                    elif tamper == "timestamp":
                        db.execute("UPDATE audit SET recorded_at=recorded_at+1 WHERE proposal_id=? AND action=?",
                                   (p["proposal_id"], "APPROVED_SANDBOX_ONLY"))
                    elif tamper == "missing":
                        db.execute("DELETE FROM audit WHERE proposal_id=? AND action=?",
                                   (p["proposal_id"], "APPROVED_SANDBOX_ONLY"))
                    else:
                        db.execute("INSERT INTO audit(proposal_id,action,actor_id,recorded_at) VALUES (?,?,?,?)",
                                   (p["proposal_id"], "APPROVED_SANDBOX_ONLY", "bob", NOW.timestamp()))
                with self.assertRaisesRegex(HITLRejected, "audit"):
                    dry_run(self.path, proposal_id=p["proposal_id"],
                            approval_token=a["approval_token"], now=NOW, **ARGS)
                with sqlite3.connect(self.path) as db:
                    self.assertEqual(db.execute("SELECT COUNT(*) FROM dry_runs WHERE proposal_id=?",
                                                (p["proposal_id"],)).fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
