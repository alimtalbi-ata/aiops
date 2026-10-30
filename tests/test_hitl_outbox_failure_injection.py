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
        first = core("acknowledge_hitl_decision_outbox", DB(("LEASED", "lease", True)))
        first_receipt = first("HDO", {"lease_token": "lease"})
        self.assertFalse(first_receipt["idempotent"])
        retry = core("acknowledge_hitl_decision_outbox", DB(("DELIVERED", None, None)))
        retry_receipt = retry("HDO", {"lease_token": "lease"})
        self.assertTrue(retry_receipt["idempotent"])
        for receipt in (first_receipt, retry_receipt):
            self.assertIs(receipt["execution_allowed"], False)
            self.assertIs(receipt["effect_allowed"], False)

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
        self.assertFalse(any("insert into" in sql.lower() for sql in db.queries))
        db, approve, payload = check("REJECT")
        with self.assertRaises(HTTPException) as ctx:
            approve("ACT", payload, authorization="offline")
        self.assertEqual((ctx.exception.status_code, ctx.exception.detail),
                         (409, "approval_nonce_reuse"))
        self.assertFalse(any("insert into" in sql.lower() for sql in db.queries))


if __name__ == "__main__":
    unittest.main()
