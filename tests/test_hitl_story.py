"""HITL Golden Demo is a real offline sandbox run, never LIVE evidence."""
import copy
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.shared.hitl_lab import HITLRejected, approve, dry_run, initialize, propose, read_status
from demo.hitl_golden_demo import build_story
from portal.hitl_demo_read_model import router, validate_story


def rehash(story):
    canonical = json.dumps({k: v for k, v in story.items() if k != "story_sha256"},
                           sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    story["story_sha256"] = hashlib.sha256(canonical).hexdigest()
    return story


class HITLStoryTests(unittest.TestCase):
    def setUp(self):
        self.story = build_story(datetime(2026, 10, 27, 21, 25, tzinfo=timezone.utc))

    def test_real_sandbox_steps_and_receipt_without_token(self):
        self.assertEqual([s["state"] for s in self.story["steps"]],
                         ["AWAITING_HUMAN_APPROVAL", "APPROVED_FOR_DRY_RUN_ONLY", "DRY_RUN_PLANNED"])
        self.assertEqual(validate_story(self.story), self.story)
        self.assertIsNone(self.story["steps"][0]["receipt_id"])
        self.assertIsNone(self.story["steps"][1]["receipt_id"])
        self.assertTrue(self.story["steps"][2]["receipt_id"])
        self.assertNotIn("approval_token", json.dumps(self.story))
        self.assertFalse(self.story["runtime_authenticated"])
        self.assertFalse(self.story["effect_executed"])
        self.assertTrue(all(v == "NOT_EXECUTED" for v in self.story["steps"][2]["postchecks"].values()))

    def test_tampered_digest_rejected(self):
        bad = copy.deepcopy(self.story)
        bad["steps"][2]["target_id"] = "ATTACKER"
        with self.assertRaises(ValueError):
            validate_story(bad)

    def test_binding_mismatch_rejected_even_with_rehashed_digest(self):
        bad = copy.deepcopy(self.story)
        bad["steps"][1]["run_id"] = "RUN-ATTACKER"
        with self.assertRaises(ValueError):
            validate_story(rehash(bad))

    def test_forged_binding_digest_rejected_even_with_rehashed_story(self):
        bad = copy.deepcopy(self.story)
        for step in bad["steps"]:
            step["binding_hash"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "binding digest mismatch"):
            validate_story(rehash(bad))

    def test_forged_parameter_hash_rejected_even_with_rehashed_story(self):
        bad = copy.deepcopy(self.story)
        for step in bad["steps"]:
            step["params_hash"] = "a" * 64
        with self.assertRaisesRegex(ValueError, "binding digest mismatch"):
            validate_story(rehash(bad))

    def test_invalid_parameter_hash_encoding_rejected(self):
        bad = copy.deepcopy(self.story)
        for step in bad["steps"]:
            step["params_hash"] = "not-a-sha256"
        with self.assertRaisesRegex(ValueError, "invalid HITL parameter digest"):
            validate_story(rehash(bad))

    def test_false_live_proof_rejected_even_with_rehashed_digest(self):
        for field in ("runtime_authenticated", "production_qualified",
                      "live_remediation_authorized", "effect_executed"):
            with self.subTest(field=field):
                bad = copy.deepcopy(self.story)
                bad[field] = True
                with self.assertRaises(ValueError):
                    validate_story(rehash(bad))

    def test_postcheck_pass_rejected(self):
        bad = copy.deepcopy(self.story)
        bad["steps"][2]["postchecks"]["service_health"] = "PASS"
        with self.assertRaises(ValueError):
            validate_story(rehash(bad))

    def test_freeform_approval_token_field_rejected(self):
        bad = copy.deepcopy(self.story)
        bad["steps"][1]["approval_token"] = "secret"
        with self.assertRaises(ValueError):
            validate_story(rehash(bad))

    def test_audit_forgery_rejected(self):
        bad = copy.deepcopy(self.story)
        bad["steps"][2]["audit_actions"] = ["PROPOSED", "DRY_RUN_PLAN_ISSUED"]
        with self.assertRaises(ValueError):
            validate_story(rehash(bad))

    def test_live_mode_rejected(self):
        bad = copy.deepcopy(self.story)
        for step in bad["steps"]:
            step["mode"] = "LIVE"
        with self.assertRaises(ValueError):
            validate_story(rehash(bad))

    def test_readonly_projection_expiry_and_redaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "lab.sqlite")
            initialize(path)
            now = datetime(2026, 10, 27, 21, 25, tzinfo=timezone.utc)
            binding = dict(incident_id="INC-1", run_id="RUN-1",
                           recipe_id="acme.demo.restart-service.v1",
                           target_id="VM-1", params={"service": "api"}, mode="DEMO")
            p = propose(path, proposer_id="alice", now=now, ttl_seconds=2, **binding)
            a = approve(path, proposal_id=p["proposal_id"], approver_id="bob",
                        approver_role="approver", now=now)
            view = read_status(path, proposal_id=p["proposal_id"], now=now)
            self.assertEqual(view["state"], "APPROVED_FOR_DRY_RUN_ONLY")
            self.assertNotIn(a["approval_token"], json.dumps(view))
            self.assertNotIn("bob", json.dumps(view))
            expired = read_status(path, proposal_id=p["proposal_id"],
                                  now=now + timedelta(seconds=2))
            self.assertEqual(expired["state"], "EXPIRED")
            self.assertFalse(expired["execution_allowed"])

    def test_readonly_missing_store_and_bad_id_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "missing.sqlite")
            with self.assertRaises(HITLRejected):
                read_status(path, proposal_id="not-found")
            self.assertFalse(Path(path).exists())
            with self.assertRaises(HITLRejected):
                read_status(path, proposal_id="bad id")

    def test_readonly_corrupted_binding_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "lab.sqlite")
            initialize(path)
            now = datetime(2026, 10, 27, 21, 25, tzinfo=timezone.utc)
            p = propose(path, incident_id="INC-1", run_id="RUN-1",
                        recipe_id="acme.demo.restart-service.v1",
                        target_id="VM-1", params={"service": "api"},
                        proposer_id="alice", now=now)
            # Simulate a corrupted/untrusted local SQLite file, not a supported
            # mutation path. Triggers protect normal writes, not hostile file owners.
            with sqlite3.connect(path) as db:
                db.execute("DROP TRIGGER proposals_immutable_update")
                db.execute("UPDATE proposals SET target_id=? WHERE proposal_id=?",
                           ("VM-FORGED", p["proposal_id"]))
            with self.assertRaisesRegex(HITLRejected, "stored proposal binding mismatch"):
                read_status(path, proposal_id=p["proposal_id"], now=now)

    def test_readonly_rejects_forged_audit_actor(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "lab.sqlite")
            initialize(path)
            now = datetime(2026, 10, 27, 21, 25, tzinfo=timezone.utc)
            binding = dict(incident_id="INC-1", run_id="RUN-1",
                           recipe_id="acme.demo.restart-service.v1",
                           target_id="VM-1", params={"service": "api"},
                           mode="DEMO")
            p = propose(path, proposer_id="alice", now=now, **binding)
            approve(path, proposal_id=p["proposal_id"], approver_id="bob",
                    approver_role="approver", now=now)
            with sqlite3.connect(path) as db:
                db.execute("DROP TRIGGER audit_immutable_update")
                db.execute("UPDATE audit SET actor_id='mallory' WHERE proposal_id=? AND action='APPROVED_SANDBOX_ONLY'",
                           (p["proposal_id"],))
            with self.assertRaisesRegex(HITLRejected, "audit actors"):
                read_status(path, proposal_id=p["proposal_id"], now=now)

    def test_readonly_rejects_forged_approver_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "lab.sqlite")
            initialize(path)
            now = datetime(2026, 10, 27, 21, 25, tzinfo=timezone.utc)
            binding = dict(incident_id="INC-1", run_id="RUN-1",
                           recipe_id="acme.demo.restart-service.v1",
                           target_id="VM-1", params={"service": "api"},
                           mode="DEMO")
            p = propose(path, proposer_id="alice", now=now, **binding)
            approve(path, proposal_id=p["proposal_id"], approver_id="bob",
                    approver_role="approver", now=now)
            with sqlite3.connect(path) as db:
                db.execute("DROP TRIGGER approvals_immutable_update")
                db.execute("UPDATE approvals SET approver_id='alice' WHERE proposal_id=?",
                           (p["proposal_id"],))
            with self.assertRaisesRegex(HITLRejected, "approval timestamp"):
                read_status(path, proposal_id=p["proposal_id"], now=now)

    def test_readonly_audit_inconsistency_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "lab.sqlite")
            initialize(path)
            now = datetime(2026, 10, 27, 21, 25, tzinfo=timezone.utc)
            p = propose(path, incident_id="INC-1", run_id="RUN-1",
                        recipe_id="acme.demo.restart-service.v1",
                        target_id="VM-1", params={"service": "api"},
                        proposer_id="alice", now=now)
            with sqlite3.connect(path) as db:
                db.execute("INSERT INTO audit(proposal_id,action,actor_id,recorded_at) VALUES(?,?,?,?)",
                           (p["proposal_id"], "FORGED", "attacker", now.timestamp()))
            with self.assertRaises(HITLRejected):
                read_status(path, proposal_id=p["proposal_id"], now=now)


    def test_readonly_rejects_forged_ttl_and_malformed_proposal_clock(self):
        now = datetime(2026, 10, 27, 21, 25, tzinfo=timezone.utc)
        binding = dict(incident_id="INC-1", run_id="RUN-1",
                       recipe_id="acme.demo.restart-service.v1",
                       target_id="VM-1", params={"service": "api"}, mode="DEMO")
        for column, value in (("expires_at", now.timestamp() + 7200),
                              ("created_at", "not-a-clock"),
                              ("expires_at", float("inf"))):
            with self.subTest(column=column, value=value), tempfile.TemporaryDirectory() as tmp:
                path = str(Path(tmp) / "lab.sqlite")
                initialize(path)
                p = propose(path, proposer_id="alice", now=now, **binding)
                approve(path, proposal_id=p["proposal_id"], approver_id="bob",
                        approver_role="approver", now=now)
                with sqlite3.connect(path) as db:
                    db.execute("DROP TRIGGER proposals_immutable_update")
                    db.execute(f"UPDATE proposals SET {column}=? WHERE proposal_id=?",
                               (value, p["proposal_id"]))
                with self.assertRaisesRegex(HITLRejected, "invalid proposal state"):
                    read_status(path, proposal_id=p["proposal_id"], now=now)

    def test_readonly_rejects_malformed_approval_or_receipt_clock(self):
        now = datetime(2026, 10, 27, 21, 25, tzinfo=timezone.utc)
        binding = dict(incident_id="INC-1", run_id="RUN-1",
                       recipe_id="acme.demo.restart-service.v1",
                       target_id="VM-1", params={"service": "api"}, mode="DEMO")
        for phase in ("approval", "receipt"):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as tmp:
                path = str(Path(tmp) / "lab.sqlite")
                initialize(path)
                p = propose(path, proposer_id="alice", now=now, **binding)
                a = approve(path, proposal_id=p["proposal_id"], approver_id="bob",
                            approver_role="approver", now=now)
                if phase == "receipt":
                    dry_run(path, proposal_id=p["proposal_id"],
                            approval_token=a["approval_token"], now=now, **binding)
                with sqlite3.connect(path) as db:
                    db.execute("DROP TRIGGER audit_immutable_update")
                    if phase == "approval":
                        db.execute("DROP TRIGGER approvals_immutable_update")
                        db.execute("UPDATE approvals SET approved_at='invalid' WHERE proposal_id=?",
                                   (p["proposal_id"],))
                        action = "APPROVED_SANDBOX_ONLY"
                    else:
                        db.execute("DROP TRIGGER dry_runs_immutable_update")
                        db.execute("UPDATE dry_runs SET consumed_at='invalid' WHERE proposal_id=?",
                                   (p["proposal_id"],))
                        action = "DRY_RUN_PLAN_ISSUED"
                    db.execute("UPDATE audit SET recorded_at='invalid' WHERE proposal_id=? AND action=?",
                               (p["proposal_id"], action))
                with self.assertRaisesRegex(HITLRejected, "invalid (approval|receipt) timestamp"):
                    read_status(path, proposal_id=p["proposal_id"], now=now)


    def test_readonly_rejects_approval_from_future_relative_to_snapshot(self):
        now = datetime(2026, 10, 27, 21, 25, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "lab.sqlite")
            initialize(path)
            p = propose(path, incident_id="INC-1", run_id="RUN-1",
                        recipe_id="acme.demo.restart-service.v1",
                        target_id="VM-1", params={"service": "api"},
                        proposer_id="alice", now=now, ttl_seconds=30)
            approve(path, proposal_id=p["proposal_id"], approver_id="bob",
                    approver_role="approver", now=now + timedelta(seconds=10))
            with self.assertRaisesRegex(HITLRejected, "invalid approval timestamp"):
                read_status(path, proposal_id=p["proposal_id"],
                            now=now + timedelta(seconds=5))
            self.assertEqual(
                read_status(path, proposal_id=p["proposal_id"],
                            now=now + timedelta(seconds=10))["state"],
                "APPROVED_FOR_DRY_RUN_ONLY")
            self.assertEqual(
                read_status(path, proposal_id=p["proposal_id"],
                            now=now + timedelta(seconds=31))["state"], "EXPIRED")

    def test_readonly_rejects_future_receipt_without_losing_historical_receipt(self):
        now = datetime(2026, 10, 27, 21, 25, tzinfo=timezone.utc)
        binding = dict(incident_id="INC-1", run_id="RUN-1",
                       recipe_id="acme.demo.restart-service.v1",
                       target_id="VM-1", params={"service": "api"}, mode="DEMO")
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "lab.sqlite")
            initialize(path)
            p = propose(path, proposer_id="alice", now=now, ttl_seconds=30, **binding)
            a = approve(path, proposal_id=p["proposal_id"], approver_id="bob",
                        approver_role="approver", now=now + timedelta(seconds=10))
            dry_run(path, proposal_id=p["proposal_id"],
                    approval_token=a["approval_token"],
                    now=now + timedelta(seconds=20), **binding)
            with self.assertRaisesRegex(HITLRejected, "invalid receipt timestamp"):
                read_status(path, proposal_id=p["proposal_id"],
                            now=now + timedelta(seconds=15))
            self.assertEqual(
                read_status(path, proposal_id=p["proposal_id"],
                            now=now + timedelta(seconds=20))["state"], "DRY_RUN_PLANNED")
            self.assertEqual(
                read_status(path, proposal_id=p["proposal_id"],
                            now=now + timedelta(seconds=31))["state"], "DRY_RUN_PLANNED")


    def test_readonly_rejects_malformed_approval_token_digest_in_both_states(self):
        now = datetime(2026, 10, 27, 21, 25, tzinfo=timezone.utc)
        binding = dict(incident_id="INC-1", run_id="RUN-1",
                       recipe_id="acme.demo.restart-service.v1",
                       target_id="VM-1", params={"service": "api"}, mode="DEMO")
        for consumed in (False, True):
            with self.subTest(consumed=consumed), tempfile.TemporaryDirectory() as tmp:
                path = str(Path(tmp) / "lab.sqlite")
                initialize(path)
                p = propose(path, proposer_id="alice", now=now, **binding)
                a = approve(path, proposal_id=p["proposal_id"], approver_id="bob",
                            approver_role="approver", now=now)
                if consumed:
                    dry_run(path, proposal_id=p["proposal_id"],
                            approval_token=a["approval_token"], now=now, **binding)
                expected = "DRY_RUN_PLANNED" if consumed else "APPROVED_FOR_DRY_RUN_ONLY"
                self.assertEqual(read_status(path, proposal_id=p["proposal_id"],
                                             now=now)["state"], expected)
                with sqlite3.connect(path) as db:
                    db.execute("DROP TRIGGER approvals_immutable_update")
                    db.execute("UPDATE approvals SET token_hash='invalid' WHERE proposal_id=?",
                               (p["proposal_id"],))
                with self.assertRaisesRegex(HITLRejected, "invalid approval token digest"):
                    read_status(path, proposal_id=p["proposal_id"], now=now)

    def test_readonly_rejects_malformed_receipt_identifiers(self):
        now = datetime(2026, 10, 27, 21, 25, tzinfo=timezone.utc)
        binding = dict(incident_id="INC-1", run_id="RUN-1",
                       recipe_id="acme.demo.restart-service.v1",
                       target_id="VM-1", params={"service": "api"}, mode="DEMO")
        for forged in ("not-a-receipt", "g" * 32, "a" * 33):
            with self.subTest(forged=forged), tempfile.TemporaryDirectory() as tmp:
                path = str(Path(tmp) / "lab.sqlite")
                initialize(path)
                p = propose(path, proposer_id="alice", now=now, **binding)
                a = approve(path, proposal_id=p["proposal_id"], approver_id="bob",
                            approver_role="approver", now=now)
                dry_run(path, proposal_id=p["proposal_id"],
                        approval_token=a["approval_token"], now=now, **binding)
                self.assertEqual(read_status(path, proposal_id=p["proposal_id"],
                                             now=now)["state"], "DRY_RUN_PLANNED")
                with sqlite3.connect(path) as db:
                    db.execute("DROP TRIGGER dry_runs_immutable_update")
                    db.execute("UPDATE dry_runs SET receipt_id=? WHERE proposal_id=?",
                               (forged, p["proposal_id"]))
                with self.assertRaisesRegex(HITLRejected, "invalid receipt identifier"):
                    read_status(path, proposal_id=p["proposal_id"], now=now)


class HITLPortalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "hitl.json"
        self.story = build_story(datetime(2026, 10, 27, 21, 25, tzinfo=timezone.utc))
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def test_not_configured_is_not_success(self):
        with patch.dict(os.environ, {"AIOPS_HITL_DEMO_ARTIFACT": ""}):
            response = self.client.get("/api/demo/hitl")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["state"], "NOT_CONFIGURED")
            self.assertEqual(response.json()["steps"], [])
            page = self.client.get("/demo/hitl")
            self.assertIn("NOT_CONFIGURED", page.text)
            self.assertNotIn("REMEDIATED", page.text)

    def test_valid_local_story_read_only(self):
        self.path.write_text(json.dumps(self.story), encoding="utf-8")
        with patch.dict(os.environ, {"AIOPS_HITL_DEMO_ARTIFACT": str(self.path)}):
            response = self.client.get("/api/demo/hitl")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["steps"][2]["state"], "DRY_RUN_PLANNED")
            self.assertEqual(response.headers["x-frame-options"], "DENY")
            page = self.client.get("/demo/hitl")
            self.assertIn("NOT_EXECUTED", page.text)
            self.assertIn("SIMULATION UNIQUEMENT", page.text)

    def test_invalid_file_and_symlink_fail_closed(self):
        self.path.write_text('{"fake":"live"}', encoding="utf-8")
        with patch.dict(os.environ, {"AIOPS_HITL_DEMO_ARTIFACT": str(self.path)}):
            self.assertEqual(self.client.get("/api/demo/hitl").status_code, 503)
        link = Path(self.tmp.name) / "symlink.json"
        link.symlink_to(self.path)
        with patch.dict(os.environ, {"AIOPS_HITL_DEMO_ARTIFACT": str(link)}):
            self.assertEqual(self.client.get("/api/demo/hitl").status_code, 503)


if __name__ == "__main__":
    unittest.main()
