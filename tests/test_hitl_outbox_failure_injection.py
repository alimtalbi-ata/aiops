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
               bearer=lambda value: value, hmac=hmac)
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
        self.assertFalse(first("HDO", {"lease_token": "lease"})["idempotent"])
        retry = core("acknowledge_hitl_decision_outbox", DB(("DELIVERED", None, None)))
        self.assertTrue(retry("HDO", {"lease_token": "lease"})["idempotent"])

    def test_dead_letter_claim_sql(self):
        db = DB()
        result = core("claim_hitl_decision_outbox", db)(
            {"owner": "offline", "limit": 1, "lease_seconds": 45})
        sql = "\n".join(db.queries).lower()
        for required in ("attempts>=20", "lease_until<=now()", "for update skip locked"):
            self.assertIn(required, sql)
        self.assertIs(result["execution_allowed"], False)

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


if __name__ == "__main__":
    unittest.main()
