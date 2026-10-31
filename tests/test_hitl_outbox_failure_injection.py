"""Offline outbox lease/ack and synthetic-approval fault injection for #194."""
import ast
import datetime
import hmac
import pathlib
import unittest
from fastapi import HTTPException

ROOT = pathlib.Path(__file__).resolve().parents[1]


class DB:
    def __init__(self, row=None):
        self.row, self.queries = row, []
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def execute(self, sql, params=()):
        self.queries.append(sql)
        return self
    def fetchone(self):
        return self.row
    def fetchall(self):
        return []


def core(name, db, **extra):
    path = "app/core/main.py"
    tree = ast.parse((ROOT / path).read_text(), filename=path)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    env = dict(Header=lambda default=None: default, HTTPException=HTTPException,
               db=lambda: db, auth=lambda token: None,
               bearer=lambda value: value, hmac=hmac, datetime=datetime)
    env.update(extra)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 path, "exec"), env)
    return env[name]


class OutboxFaultTests(unittest.TestCase):
    def test_malformed_outbox_claim_lease_fence(self):
        # Reject forged/malformed lease requests before any DB or Temporal activity.
        for payload in (
            {"owner": "", "limit": 1, "lease_seconds": 45},
            {"owner": "offline", "limit": True, "lease_seconds": 45},
            {"owner": "offline", "limit": 0, "lease_seconds": 45},
            {"owner": "offline", "limit": 101, "lease_seconds": 45},
            {"owner": "offline", "limit": 1, "lease_seconds": True},
            {"owner": "offline", "limit": 1, "lease_seconds": 45.0},
            {"owner": "offline", "limit": 1, "lease_seconds": 14},
            {"owner": "offline", "limit": 1, "lease_seconds": 301},
        ):
            with self.subTest(payload=payload):
                db = DB()
                with self.assertRaises(HTTPException) as ctx:
                    core("claim_hitl_decision_outbox", db)(payload)
                self.assertEqual(ctx.exception.status_code, 422)
                self.assertEqual(db.queries, [])

    def test_nonleased_dead_and_missing_token_ack_are_fenced(self):
        # A stale, dead-lettered or unowned event cannot be ACKed as delivered.
        for row in (
            ("PENDING", "lease", True),
            ("DEAD", "lease", True),
            ("LEASED", None, True),
            ("LEASED", "lease", False),
        ):
            with self.subTest(row=row):
                db = DB(row)
                with self.assertRaises(HTTPException) as ctx:
                    core("acknowledge_hitl_decision_outbox", db)(
                        "HDO-OFFLINE", {"lease_token": "lease"})
                self.assertEqual((ctx.exception.status_code, ctx.exception.detail),
                                 (409, "outbox_lease_lost_or_invalid"))
                self.assertFalse(any("set status='DELIVERED'" in s for s in db.queries))

    def test_expired_lease(self):
        db = DB(("LEASED", "lease", False))
        with self.assertRaises(HTTPException) as ctx:
            core("acknowledge_hitl_decision_outbox", db)("HDO", {"lease_token": "lease"})
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertFalse(any("set status='DELIVERED'" in s for s in db.queries))

    def test_lost_lease(self):
        with self.assertRaises(HTTPException) as ctx:
            core("acknowledge_hitl_decision_outbox", DB(("LEASED", "new", True)))(
                "HDO", {"lease_token": "old"})
        self.assertEqual(ctx.exception.status_code, 409)

    def test_lost_ack_retry(self):
        first_db = DB(("LEASED", "lease", True))
        first = core("acknowledge_hitl_decision_outbox", first_db)
        first_receipt = first("HDO", {"lease_token": "lease"})
        self.assertFalse(first_receipt["idempotent"])
        updates = [sql for sql in first_db.queries if "set status='DELIVERED'" in sql]
        self.assertEqual(len(updates), 1)
        # Preserve the original lease token as an idempotency fence after ACK.
        self.assertNotIn("lease_token=null", updates[0])
        retry_db = DB(("DELIVERED", "lease", None))
        retry = core("acknowledge_hitl_decision_outbox", retry_db)
        retry_receipt = retry("HDO", {"lease_token": "lease"})
        self.assertTrue(retry_receipt["idempotent"])
        self.assertFalse(any("set status='DELIVERED'" in sql for sql in retry_db.queries))
        for receipt in (first_receipt, retry_receipt):
            self.assertIs(receipt["execution_allowed"], False)
            self.assertIs(receipt["effect_allowed"], False)

    def test_delivered_ack_replay_with_wrong_or_missing_original_lease_is_fenced(self):
        # An event already DELIVERED is not a free ACK oracle for any token.
        # These are scripted rows, never a PostgreSQL or Temporal integration.
        for stored_token, supplied_token in (
            (None, "old"),
            ("original", "different"),
            ("original", "ORIGINAL"),
        ):
            with self.subTest(stored_token=stored_token, supplied_token=supplied_token):
                db = DB(("DELIVERED", stored_token, None))
                with self.assertRaises(HTTPException) as ctx:
                    core("acknowledge_hitl_decision_outbox", db)(
                        "HDO-OFFLINE", {"lease_token": supplied_token})
                self.assertEqual((ctx.exception.status_code, ctx.exception.detail),
                                 (409, "outbox_lease_lost_or_invalid"))
                self.assertFalse(any("set status='DELIVERED'" in sql for sql in db.queries))

    def test_dead_letter_claim_sql(self):
        db = DB()
        result = core("claim_hitl_decision_outbox", db)(
            {"owner": "offline", "limit": 1, "lease_seconds": 45})
        sql = "\n".join(db.queries).lower()
        for required in ("attempts>=20", "lease_until<=now()", "for update skip locked"):
            self.assertIn(required, sql)
        self.assertIs(result["execution_allowed"], False)
        self.assertIs(result["effect_allowed"], False)

    def test_outbox_status_is_not_an_authorization(self):
        receipt = core("hitl_decision_outbox_status", DB())(authorization="offline")
        self.assertEqual(receipt["counts"], {})
        self.assertIs(receipt["execution_allowed"], False)
        self.assertIs(receipt["effect_allowed"], False)

    def test_synthetic_approval_forbidden(self):
        db = DB(("RUN", "DEMO", "CI", "COLLECT_DIAGNOSTICS", "LOW",
                 "hash", "PROPOSED",
                 datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10), 1))
        approve = core("record_proposal_approval", db, IdentityError=ValueError,
                       require_live_assertion=lambda token: {
                           "subject_id": "oidc:offline", "roles": ["operator"]})
        with self.assertRaises(HTTPException) as ctx:
            approve("ACT", {"proposal_hash": "hash", "actor_role": "operator",
                            "decision": "APPROVE", "nonce": "offline", "scope": {}},
                    authorization="offline")
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail, "synthetic_mode_cannot_authorize_real_approval")
        self.assertFalse(any("insert into" in s.lower() for s in db.queries))


    def test_oidc_role_escalation_rejected_before_db(self):
        # The browser-supplied role cannot exceed verified OIDC entitlements.
        db = DB()
        approve = core("record_proposal_approval", db, IdentityError=ValueError,
                       require_live_assertion=lambda token: {
                           "subject_id": "oidc:offline", "roles": ["operator"]})
        with self.assertRaises(HTTPException) as ctx:
            approve("ACT", {"proposal_hash": "hash", "actor_role": "security_admin",
                            "decision": "APPROVE", "nonce": "offline-role", "scope": {}},
                    authorization="offline")
        self.assertEqual((ctx.exception.status_code, ctx.exception.detail),
                         (403, "requested_approval_role_not_in_verified_oidc_entitlements"))
        self.assertEqual(db.queries, [])

    def test_proposal_hash_and_scope_mismatch_never_write(self):
        # In-memory LIVE-labelled row exercises a denial branch; no real LIVE call.
        future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)
        row = ("RUN", "LIVE", "CI", "COLLECT_DIAGNOSTICS", "LOW",
               "hash", "PROPOSED", future, 1)
        exact = {"proposal_hash": "hash", "target_ci_id": "CI",
                 "action_type": "COLLECT_DIAGNOSTICS"}
        for digest, scope, detail in (
            ("stale-hash", exact, "proposal_hash_mismatch"),
            ("hash", {"proposal_hash": "hash", "target_ci_id": "OTHER",
                      "action_type": "COLLECT_DIAGNOSTICS"},
             "approval_scope_must_match_exact_proposal"),
        ):
            with self.subTest(detail=detail):
                db = DB(row)
                approve = core("record_proposal_approval", db, IdentityError=ValueError,
                               require_live_assertion=lambda token: {
                                   "subject_id": "oidc:offline", "roles": ["operator"]})
                with self.assertRaises(HTTPException) as ctx:
                    approve("ACT", {"proposal_hash": digest, "actor_role": "operator",
                                    "decision": "APPROVE", "nonce": "offline-scope",
                                    "scope": scope}, authorization="offline")
                self.assertEqual((ctx.exception.status_code, ctx.exception.detail), (409 if detail == "proposal_hash_mismatch" else 422, detail))
                self.assertFalse(any("insert into" in sql.lower() for sql in db.queries))

    def test_expired_proposal_rejected_without_decision_write(self):
        # Scripted DB responses: proposal row then no nonce collision.
        class ScriptedDB(DB):
            def __init__(self, rows):
                super().__init__()
                self.rows = list(rows)
            def fetchone(self):
                return self.rows.pop(0) if self.rows else None
        expired = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)
        db = ScriptedDB([("RUN", "LIVE", "CI", "COLLECT_DIAGNOSTICS",
                          "LOW", "hash", "PROPOSED", expired, 1), None])
        approve = core("record_proposal_approval", db, IdentityError=ValueError,
                       require_live_assertion=lambda token: {
                           "subject_id": "oidc:offline", "roles": ["operator"]})
        with self.assertRaises(HTTPException) as ctx:
            approve("ACT", {"proposal_hash": "hash", "actor_role": "operator",
                            "decision": "APPROVE", "nonce": "offline-expired",
                            "scope": {"proposal_hash": "hash", "target_ci_id": "CI",
                                      "action_type": "COLLECT_DIAGNOSTICS"}},
                    authorization="offline")
        self.assertEqual((ctx.exception.status_code, ctx.exception.detail),
                         (409, "proposal_expired"))
        self.assertFalse(any("insert into" in sql.lower() for sql in db.queries))

    def test_nonce_replay_is_idempotent_only_for_identical_decision(self):
        import json
        class ScriptedDB(DB):
            def __init__(self, rows):
                super().__init__()
                self.rows = list(rows)
            def fetchone(self):
                return self.rows.pop(0) if self.rows else None
        future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)
        proposal = ("RUN", "LIVE", "CI", "COLLECT_DIAGNOSTICS",
                    "LOW", "hash", "PROPOSED", future, 1)
        scope = {"proposal_hash": "hash", "target_ci_id": "CI",
                 "action_type": "COLLECT_DIAGNOSTICS"}
        prior = ("APR-OFFLINE", "ACT", "hash", "APPROVE", "oidc:offline",
                 "operator", json.dumps(scope), json.dumps({}))
        def check(decision):
            db = ScriptedDB([proposal, prior])
            approve = core("record_proposal_approval", db, IdentityError=ValueError,
                           json=json, require_live_assertion=lambda token: {
                               "subject_id": "oidc:offline", "roles": ["operator"]})
            payload = {"proposal_hash": "hash", "actor_role": "operator",
                       "decision": decision, "nonce": "offline-replay", "scope": scope}
            return db, approve, payload
        db, approve, payload = check("APPROVE")
        receipt = approve("ACT", payload, authorization="offline")
        self.assertIs(receipt["idempotent"], True)
        self.assertIs(receipt["execution_allowed"], False)
        self.assertIs(receipt["effect_allowed"], False)
        self.assertFalse(any("insert into" in sql.lower() for sql in db.queries))
        db, approve, payload = check("REJECT")
        with self.assertRaises(HTTPException) as ctx:
            approve("ACT", payload, authorization="offline")
        self.assertEqual((ctx.exception.status_code, ctx.exception.detail),
                         (409, "approval_nonce_reuse"))
        self.assertFalse(any("insert into" in sql.lower() for sql in db.queries))


    def test_proposal_idempotent_and_new_receipts_are_no_effect(self):
        # Exercise both Core proposal return paths against scripted memory only.
        # No database, authentication service, or LIVE workflow is contacted.
        import json

        class ProposalDB(DB):
            def __init__(self, existing):
                super().__init__()
                self.existing = existing
                self.current = None

            def execute(self, sql, params=()):
                self.queries.append(sql)
                if "select mode from aiops.runs" in sql:
                    self.current = ("DEMO",)
                elif "select a.output" in sql:
                    self.current = (
                        {"recommended_actions": [{
                            "action_id": "SRC", "advisory_only": True,
                            "requires_human_approval": True, "risk_tier": "LOW",
                            "target_ci_id": "CI",
                        }]}, ["E"], "VALID", True, ["E"],
                        {"issues": [], "unsafe_actions": []},
                    )
                elif "select count(*) from aiops.evidence" in sql:
                    self.current = (1,)
                elif "select proposal_id,proposal_revision,status" in sql:
                    self.current = ("ACT-OFFLINE", 1, "PROPOSED") if self.existing else None
                elif "select coalesce(max(proposal_revision)" in sql:
                    self.current = (1,)
                elif "insert into aiops.action_proposals" in sql:
                    self.current = None
                else:
                    raise AssertionError("unexpected_scripted_sql")
                return self

            def fetchone(self):
                return self.current

        payload = {
            "target_ci_id": "CI", "action_type": "COLLECT_DIAGNOSTICS",
            "risk_tier": "LOW", "source_action_id": "SRC",
            "analysis_id": "A", "critique_id": "C",
            "evidence_ids": ["E"], "preconditions": ["pre"],
            "expected_postconditions": ["post"],
        }
        for existing in (True, False):
            with self.subTest(existing=existing):
                db = ProposalDB(existing)
                create = core(
                    "create_action_proposal", db, json=json,
                    canonical_sha256=lambda data: "hash-offline",
                    PROPOSAL_ACTION_ALLOWLIST={"COLLECT_DIAGNOSTICS"},
                    APPROVER_ROLES={"LOW": ("operator",)},
                    new=lambda prefix: "ACT-OFFLINE",
                )
                receipt = create("RUN-OFFLINE", payload, authorization="offline")
                self.assertEqual(receipt["status"], "PROPOSED")
                self.assertEqual(receipt["proposal_hash"], "hash-offline")
                self.assertIs(receipt["idempotent"], existing)
                self.assertIs(receipt["execution_allowed"], False)
                self.assertIs(receipt["effect_allowed"], False)
                writes = [sql for sql in db.queries if sql.startswith("insert into")]
                self.assertEqual(len(writes), 0 if existing else 1)



if __name__ == "__main__":
    unittest.main()
