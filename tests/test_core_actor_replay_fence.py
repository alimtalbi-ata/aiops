"""Adversarial, no-network Core actor JTI/nonce decision wiring tests."""
import hashlib
import json
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch

from core import actor_replay_fence as fence
from core import itsm_xref as x

NOW = 1793509000
EXPECTED = {
    "tenant_id": "TEN-A", "run_id": "RUN-A", "incident_id": "INC-A",
    "glpi_instance_id": "GLPI-A", "ticket_id": "123", "glpi_entity_id": "7",
    "permission": "run:read", "nonce": "nonce_012345678901234567890123",
}
CLAIMS = {"iss": "https://idp.example.invalid", "sub": "subject-A",
          "jti": "jti_012345678901234567890123", "exp": NOW + 60}


class FakeConnection:
    def __init__(self, answer=True, fail=False):
        self.answer = answer
        self.fail = fail
        self.calls = []
    def execute(self, sql, args):
        self.calls.append((sql, args))
        if self.fail:
            raise RuntimeError("disposable PG unavailable")
        return self
    def fetchone(self):
        return (self.answer,)


class ActorReplayFenceTests(unittest.TestCase):
    def setUp(self):
        self.conn = FakeConnection()
        @contextmanager
        def db():
            yield self.conn
        self.db_patch = patch.object(x, "db", db)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)

    def test_atomic_pg_function_exact_scope_and_expiry(self):
        self.assertTrue(fence.consume_actor_delegation(CLAIMS, EXPECTED, NOW))
        self.assertEqual(len(self.conn.calls), 1)
        statement, args = self.conn.calls[0]
        self.assertEqual(statement.count("%s"), 7)
        self.assertIn("aiops.actor_delegation_consume", statement)
        self.assertEqual(args[0], "TEN-A")
        self.assertEqual(args[1], CLAIMS["iss"])
        self.assertEqual(args[2], hashlib.sha256(b"subject-A").hexdigest())
        self.assertEqual(args[3], hashlib.sha256(CLAIMS["jti"].encode()).hexdigest())
        self.assertEqual(args[4], hashlib.sha256(EXPECTED["nonce"].encode()).hexdigest())
        self.assertEqual(args[5], fence._resource_digest(EXPECTED))
        self.assertEqual(args[6], datetime.fromtimestamp(CLAIMS["exp"], tz=timezone.utc))

    def test_cross_tenant_run_ticket_entity_permission_nonce_rekeys_digest(self):
        baseline = fence._resource_digest(EXPECTED)
        for key, value in (("tenant_id", "TEN-B"), ("run_id", "RUN-B"),
                           ("incident_id", "INC-B"), ("glpi_instance_id", "GLPI-B"),
                           ("ticket_id", "124"), ("glpi_entity_id", "8"),
                           ("permission", "ticket:write"), ("nonce", "other-nonce")):
            with self.subTest(key=key):
                self.assertNotEqual(fence._resource_digest({**EXPECTED, key: value}),
                                    baseline)

    def test_replay_revocation_and_db_error_never_become_true(self):
        self.conn.answer = False
        self.assertFalse(fence.consume_actor_delegation(CLAIMS, EXPECTED, NOW))
        self.conn.fail = True
        self.assertIsNone(fence.consume_actor_delegation(CLAIMS, EXPECTED, NOW))
        self.conn.fail = False
        self.conn.answer = None
        self.assertFalse(fence.consume_actor_delegation(CLAIMS, EXPECTED, NOW))

    def test_expired_missing_or_forged_claims_never_query_db(self):
        for claims, expected in (
            ({**CLAIMS, "exp": NOW}, EXPECTED),
            ({**CLAIMS, "exp": NOW + 301}, EXPECTED),
            ({**CLAIMS, "exp": True}, EXPECTED),
            ({**CLAIMS, "jti": ""}, EXPECTED),
            ({**CLAIMS, "sub": None}, EXPECTED),
            (CLAIMS, {**EXPECTED, "ticket_id": None}),
            (CLAIMS, {k: v for k, v in EXPECTED.items() if k != "nonce"}),
        ):
            with self.subTest(claims=claims, expected=expected):
                self.assertFalse(fence.consume_actor_delegation(claims, expected, NOW))
        self.assertEqual(self.conn.calls, [])

    def test_scope_is_canonical_and_domain_separated(self):
        raw = json.dumps({"schema": fence.SCHEMA, "scope": EXPECTED},
                         sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        self.assertEqual(fence._resource_digest(EXPECTED),
                         hashlib.sha256(raw.encode("utf-8")).hexdigest())


if __name__ == "__main__":
    unittest.main()
