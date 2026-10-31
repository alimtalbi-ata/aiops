"""PostgreSQL 16 disposable HITL outbox handler tests; no LIVE/identity/effects.

Runs Core's actual claim/ack functions with a CI-only database. Authentication is
stubbed, so this qualifies lease SQL, not OIDC or approval authority.
"""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import unittest
import uuid

import psycopg
from fastapi import HTTPException
from test_hitl_outbox_failure_injection import core


def db():
    return psycopg.connect(host="127.0.0.1", port=5432, dbname="aiops", user="aiops",
                           password=os.environ["PGPASSWORD"], connect_timeout=5)


class Connection:
    def __enter__(self):
        self.connection = db()
        return self.connection.__enter__()

    def __exit__(self, *args):
        return self.connection.__exit__(*args)


def claim(owner):
    receipt = core("claim_hitl_decision_outbox", Connection(), uuid=uuid)(
        {"owner": owner, "limit": 1, "lease_seconds": 15})
    assert receipt["execution_allowed"] is False and receipt["effect_allowed"] is False
    return receipt["items"]


def ack(event, token):
    receipt = core("acknowledge_hitl_decision_outbox", Connection())(
        event, {"lease_token": token})
    assert receipt["execution_allowed"] is False and receipt["effect_allowed"] is False
    return receipt


def fixture(decision="REJECT"):
    """Create a synthetic decision notification, never a verified human approval."""
    if decision not in ("REJECT", "APPROVE"):
        raise ValueError("synthetic_fixture_decision_must_be_reject_or_approve")
    proposal_status = "APPROVED" if decision == "APPROVE" else "REJECTED"
    suffix = uuid.uuid4().hex
    run, analysis, critique = ("CI-HITL-RUN-" + suffix,
                               "CI-HITL-AN-" + suffix, "CI-HITL-CR-" + suffix)
    proposal, approval, event = ("CI-HITL-ACT-" + suffix,
                                 "CI-HITL-APR-" + suffix, "CI-HITL-HDO-" + suffix)
    evidence = "CI-HITL-EVD-" + suffix
    digest = hashlib.sha256(("SYNTHETIC_UNVERIFIED:" + suffix).encode()).hexdigest()
    evidence_ids = json.dumps([evidence])
    action = {"action_id": "CI-FIXTURE", "risk_tier": "LOW",
              "target_ci_id": "CI-SYNTHETIC", "advisory_only": True,
              "requires_human_approval": True}
    with db() as c:
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
                  "'ci_fixture',%s,%s,now()+interval '1 hour',%s)",
                  (approval, proposal, digest, decision, "ci-nonce-" + suffix,
                   json.dumps({"synthetic": True, "identity_attested": False})))
        c.execute("update aiops.action_proposals set status=%s "
                  "where proposal_id=%s", (proposal_status, proposal))
        c.execute("insert into aiops.hitl_decision_outbox "
                  "(event_id,proposal_id,run_id,proposal_hash,proposal_revision,"
                  "decision,source_status,approval_id) "
                  "values(%s,%s,%s,%s,1,%s,%s,%s)",
                  (event, proposal, run, digest, decision, proposal_status, approval))
    return event, proposal

class PostgreSQL16OutboxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        required = {"AIOPS_CI_OUTBOX_DISPOSABLE": "YES", "GITHUB_ACTIONS": "true",
                    "PGHOST": "127.0.0.1", "PGPORT": "5432", "PGDATABASE": "aiops",
                    "PGUSER": "aiops"}
        if any(os.environ.get(k) != v for k, v in required.items()):
            raise RuntimeError("refuse_non_disposable_postgres")
        with db() as c:
            if not str(c.execute("show server_version_num").fetchone()[0]).startswith("16"):
                raise RuntimeError("requires_postgresql_16")

    def no_effect(self, proposal):
        with db() as c:
            self.assertEqual(c.execute("select count(*) from aiops.effect_receipts "
                                       "where proposal_id=%s", (proposal,)).fetchone()[0], 0)

    def test_synthetic_approve_outbox_notification_is_not_authorization(self):
        """Even an APPROVE-shaped Temporal notification cannot grant authority.

        This deliberately seeds a synthetic, unverified approval in disposable
        PostgreSQL; it does not exercise a real OIDC identity or HITL decision.
        """
        event, proposal = fixture(decision="APPROVE")
        items = claim("ci-approve-is-not-authority")
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual((item["event_id"], item["decision"],
                          item["source_status"], item["proposal_revision"]),
                         (event, "APPROVE", "APPROVED", 1))
        with db() as c:
            row = c.execute(
                "select r.mode,a.actor_id,a.audit->>'identity_attested',"
                "a.audit->>'synthetic' from aiops.hitl_decision_outbox o "
                "join aiops.runs r on r.run_id=o.run_id "
                "join aiops.approval_records a on a.approval_id=o.approval_id "
                "where o.event_id=%s", (event,)).fetchone()
        self.assertEqual(row, ("DEMO", "SYNTHETIC_UNVERIFIED", "false", "true"))
        receipt = ack(event, item["lease_token"])
        self.assertEqual((receipt["status"], receipt["idempotent"]),
                         ("DELIVERED", False))
        self.assertTrue(ack(event, item["lease_token"])["idempotent"])
        self.assertEqual(claim("ci-approve-after-ack"), [])
        self.no_effect(proposal)

    def test_concurrent_claim_single_winner(self):
        event, proposal = fixture()
        barrier = threading.Barrier(2)
        def contender(n):
            barrier.wait(timeout=10)
            return claim("ci-concurrent-" + str(n))
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(contender, n) for n in (1, 2)]
            items = [x for future in futures for x in future.result(timeout=15)]
        self.assertEqual(len(items), 1)
        self.assertEqual((items[0]["event_id"], items[0]["attempts"]), (event, 1))
        self.assertFalse(ack(event, items[0]["lease_token"])["idempotent"])
        self.no_effect(proposal)

    def test_skip_locked_row(self):
        event, proposal = fixture()
        with db() as locked:
            locked.execute("select event_id from aiops.hitl_decision_outbox "
                           "where event_id=%s for update", (event,))
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                self.assertEqual(pool.submit(claim, "ci-locked").result(timeout=10), [])
        token = claim("ci-after-unlock")[0]["lease_token"]
        ack(event, token)
        self.no_effect(proposal)

    def test_lost_ack_lease_expiry_reclaim_and_replay(self):
        event, proposal = fixture()
        old = claim("ci-before-restart")[0]
        with db() as c:
            c.execute("update aiops.hitl_decision_outbox "
                      "set lease_until=now()-interval '1 second' where event_id=%s", (event,))
        with self.assertRaises(HTTPException) as error:
            ack(event, old["lease_token"])
        self.assertEqual(error.exception.status_code, 409)
        new = claim("ci-after-restart")[0]  # fresh handler and DB connection
        self.assertEqual(new["attempts"], 2)
        self.assertNotEqual(old["lease_token"], new["lease_token"])
        with self.assertRaises(HTTPException):
            ack(event, old["lease_token"])
        self.assertFalse(ack(event, new["lease_token"])["idempotent"])
        self.assertTrue(ack(event, new["lease_token"])["idempotent"])
        with self.assertRaises(HTTPException):
            ack(event, "forged-token")
        with db() as c:
            status, digest = c.execute("select status,lease_token from "
                "aiops.hitl_decision_outbox where event_id=%s", (event,)).fetchone()
        self.assertEqual(status, "DELIVERED")
        self.assertEqual(digest, hashlib.sha256(new["lease_token"].encode()).hexdigest())
        self.no_effect(proposal)

    def test_concurrent_expired_lease_takeover_fences_stale_ack(self):
        """Two fresh claimers race a lost ACK; only the new lease may ACK."""
        event, proposal = fixture()
        old = claim("ci-lost-ack-original")[0]
        with db() as c:
            c.execute("update aiops.hitl_decision_outbox "
                      "set lease_until=now()-interval '1 second' where event_id=%s",
                      (event,))
        barrier = threading.Barrier(2)
        def contender(n):
            barrier.wait(timeout=10)
            return claim("ci-takeover-" + str(n))
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(contender, n) for n in (1, 2)]
            winners = [item for future in futures
                       for item in future.result(timeout=15)]
        self.assertEqual(len(winners), 1)
        new = winners[0]
        self.assertEqual((new["event_id"], new["attempts"]), (event, 2))
        self.assertNotEqual(old["lease_token"], new["lease_token"])
        with self.assertRaises(HTTPException) as stale:
            ack(event, old["lease_token"])
        self.assertEqual(stale.exception.status_code, 409)
        self.assertFalse(ack(event, new["lease_token"])["idempotent"])
        self.assertTrue(ack(event, new["lease_token"])["idempotent"])
        self.assertEqual(claim("ci-after-takeover"), [])
        with db() as c:
            state = c.execute("select status,attempts,lease_token from "
                              "aiops.hitl_decision_outbox where event_id=%s",
                              (event,)).fetchone()
        self.assertEqual(state, ("DELIVERED", 2,
                         hashlib.sha256(new["lease_token"].encode()).hexdigest()))
        self.no_effect(proposal)

    def test_retry_dead_letter(self):
        event, proposal = fixture()
        with db() as c:
            c.execute("update aiops.hitl_decision_outbox set status='LEASED',"
                      "attempts=19,lease_owner='ci',lease_token='old',"
                      "lease_until=now()-interval '1 second' where event_id=%s", (event,))
        last = claim("ci-attempt-20")[0]
        self.assertEqual(last["attempts"], 20)
        with db() as c:
            c.execute("update aiops.hitl_decision_outbox "
                      "set lease_until=now()-interval '1 second' where event_id=%s", (event,))
        self.assertEqual(claim("ci-dead"), [])
        with db() as c:
            state = c.execute("select status,attempts,last_error from "
                              "aiops.hitl_decision_outbox where event_id=%s", (event,)).fetchone()
        self.assertEqual(state, ("DEAD", 20, "delivery_attempt_limit_exceeded"))
        with self.assertRaises(HTTPException):
            ack(event, last["lease_token"])
        self.no_effect(proposal)

    def test_concurrent_duplicate_ack_is_serialized(self):
        """Concurrent ACKs on one lease commit once, then become idempotent."""
        event, proposal = fixture()
        token = claim("ci-parallel-ack")[0]["lease_token"]
        barrier = threading.Barrier(2)

        def contender():
            barrier.wait(timeout=10)
            return ack(event, token)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(contender) for _ in range(2)]
            receipts = [future.result(timeout=15) for future in futures]
        self.assertEqual(sorted(r["idempotent"] for r in receipts), [False, True])
        self.assertTrue(all(r["event_id"] == event and r["status"] == "DELIVERED"
                            for r in receipts))
        self.assertEqual(claim("ci-after-parallel-ack"), [])
        self.no_effect(proposal)

    def test_duplicate_ack_and_no_redelivery(self):
        event, proposal = fixture()
        token = claim("ci-duplicate")[0]["lease_token"]
        self.assertFalse(ack(event, token)["idempotent"])
        self.assertTrue(ack(event, token)["idempotent"])
        self.assertEqual(claim("ci-no-redelivery"), [])
        self.no_effect(proposal)


    def test_pending_event_is_not_claimable_before_available_at(self):
        """Backoff/availability gate cannot be bypassed by an eager poller."""
        event, proposal = fixture()
        with db() as c:
            c.execute("update aiops.hitl_decision_outbox "
                      "set available_at=now()+interval '10 minutes' where event_id=%s",
                      (event,))
        self.assertEqual(claim("ci-before-available"), [])
        with db() as c:
            state = c.execute("select status,attempts from aiops.hitl_decision_outbox "
                              "where event_id=%s", (event,)).fetchone()
            self.assertEqual(state, ("PENDING", 0))
            c.execute("update aiops.hitl_decision_outbox "
                      "set available_at=now()-interval '1 second' where event_id=%s",
                      (event,))
        item = claim("ci-after-available")[0]
        self.assertEqual((item["event_id"], item["attempts"]), (event, 1))
        self.assertFalse(ack(event, item["lease_token"])["idempotent"])
        self.no_effect(proposal)

    def test_unexpired_lease_cannot_be_stolen_or_acked_with_wrong_token(self):
        """No duplicate delivery while a valid lease is still outstanding."""
        event, proposal = fixture()
        first = claim("ci-valid-lease")[0]
        self.assertEqual(claim("ci-premature-takeover"), [])
        with self.assertRaises(HTTPException) as forged:
            ack(event, "forged-token")
        self.assertEqual(forged.exception.status_code, 409)
        with db() as c:
            state = c.execute("select status,attempts,lease_token from "
                              "aiops.hitl_decision_outbox where event_id=%s",
                              (event,)).fetchone()
        self.assertEqual(state, ("LEASED", 1, first["lease_token"]))
        self.assertFalse(ack(event, first["lease_token"])["idempotent"])
        self.assertEqual(claim("ci-after-valid-ack"), [])
        self.no_effect(proposal)

    def test_dead_letter_exhaustion_does_not_starve_healthy_event(self):
        """A poisoned expired lease is DEAD, not a blocker for independent REJECT."""
        exhausted, exhausted_proposal = fixture()
        healthy, healthy_proposal = fixture()
        with db() as c:
            c.execute("update aiops.hitl_decision_outbox "
                      "set status='LEASED',attempts=20,lease_owner='ci-exhausted',"
                      "lease_token='expired-token',"
                      "lease_until=now()-interval '1 second' where event_id=%s",
                      (exhausted,))
        items = claim("ci-independent-healthy")
        self.assertEqual(len(items), 1)
        self.assertEqual((items[0]["event_id"], items[0]["attempts"]),
                         (healthy, 1))
        with db() as c:
            state = c.execute("select status,attempts,last_error from "
                              "aiops.hitl_decision_outbox where event_id=%s",
                              (exhausted,)).fetchone()
        self.assertEqual(state, ("DEAD", 20, "delivery_attempt_limit_exceeded"))
        with self.assertRaises(HTTPException) as stale:
            ack(exhausted, "expired-token")
        self.assertEqual(stale.exception.status_code, 409)
        self.assertFalse(ack(healthy, items[0]["lease_token"])["idempotent"])
        self.assertEqual(claim("ci-after-dead-letter"), [])
        self.no_effect(exhausted_proposal)
        self.no_effect(healthy_proposal)


    def test_concurrent_batch_claims_partition_three_events_without_duplicates(self):
        """Two claimers with limit=2 partition three committed synthetic REJECTs."""
        fixtures = [fixture() for _ in range(3)]
        expected = {event for event, _ in fixtures}
        barrier = threading.Barrier(2)

        def contender(n):
            barrier.wait(timeout=10)
            receipt = core("claim_hitl_decision_outbox", Connection(), uuid=uuid)(
                {"owner": "ci-batch-" + str(n), "limit": 2, "lease_seconds": 15})
            assert receipt["execution_allowed"] is False
            assert receipt["effect_allowed"] is False
            assert receipt["count"] == len(receipt["items"])
            return receipt["items"]

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(contender, n) for n in (1, 2)]
            batches = [future.result(timeout=15) for future in futures]
        self.assertEqual(sorted(map(len, batches)), [1, 2])
        items = [item for batch in batches for item in batch]
        self.assertEqual({item["event_id"] for item in items}, expected)
        self.assertEqual(len(items), len(expected))  # No double lease.
        self.assertTrue(all(item["decision"] == "REJECT"
                            and item["attempts"] == 1 for item in items))
        for item in items:
            receipt = ack(item["event_id"], item["lease_token"])
            self.assertEqual((receipt["status"], receipt["idempotent"]),
                             ("DELIVERED", False))
        self.assertEqual(claim("ci-batch-after-delivery"), [])
        with db() as c:
            rows = c.execute(
                "select event_id,status,attempts from aiops.hitl_decision_outbox "
                "where event_id=any(%s)", (list(expected),)).fetchall()
        self.assertEqual({(event, status, attempts) for event, status, attempts in rows},
                         {(event, "DELIVERED", 1) for event in expected})
        for _, proposal in fixtures:
            self.no_effect(proposal)

    def test_lost_ack_response_after_commit_is_idempotent(self):
        """Simulate lost HTTP response after Core committed DELIVERED, no redelivery."""
        event, proposal = fixture()
        first = claim("ci-ack-response-lost")[0]
        ack(event, first["lease_token"])  # Core committed; discard response
        self.assertEqual(claim("ci-after-lost-ack-response"), [])
        replay = ack(event, first["lease_token"])
        self.assertEqual((replay["event_id"], replay["status"], replay["idempotent"]),
                         (event, "DELIVERED", True))
        with db() as c:
            status, attempts, stored = c.execute(
                "select status,attempts,lease_token from aiops.hitl_decision_outbox "
                "where event_id=%s", (event,)).fetchone()
        self.assertEqual((status, attempts, stored),
                         ("DELIVERED", 1,
                          hashlib.sha256(first["lease_token"].encode()).hexdigest()))
        self.no_effect(proposal)

    def test_lease_tokens_are_scoped_to_exact_event(self):
        """A valid lease for one synthetic REJECT cannot ACK another event."""
        first_event, first_proposal = fixture()
        second_event, second_proposal = fixture()
        first = claim("ci-event-binding-first")[0]
        second = claim("ci-event-binding-second")[0]
        self.assertEqual((first["event_id"], second["event_id"]),
                         (first_event, second_event))
        for event_id, wrong_token in (
                (first_event, second["lease_token"]),
                (second_event, first["lease_token"])):
            with self.subTest(event_id=event_id):
                with self.assertRaises(HTTPException) as error:
                    ack(event_id, wrong_token)
                self.assertEqual(error.exception.status_code, 409)
        self.assertFalse(ack(first_event, first["lease_token"])["idempotent"])
        self.assertFalse(ack(second_event, second["lease_token"])["idempotent"])
        self.assertEqual(claim("ci-after-event-bound-acks"), [])
        self.no_effect(first_proposal)
        self.no_effect(second_proposal)


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(PostgreSQL16OutboxTests))
    Path("reports").mkdir(exist_ok=True)
    Path("reports/hitl-pg16-outbox.json").write_text(json.dumps({
        "status": "PASS" if result.wasSuccessful() else "FAIL",
        "tests_run": result.testsRun,
        "tests_passed": result.testsRun - len(result.failures) - len(result.errors),
        "mode": "DEMO synthetic fixture", "identity": "NOT_ATTESTED",
        "temporal_signal": "NOT_TESTED", "execution_allowed": False,
        "effect_allowed": False}, indent=2) + "\n", encoding="utf-8")
    sys.exit(0 if result.wasSuccessful() else 1)
