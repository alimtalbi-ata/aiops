"""The source-only authority boundary must never grant browser evidence or actions."""
import unittest

from scripts.acme_server_authority_boundary import authorize_acme_view


class ExplodingIdentity:
    def authenticated_actor(self, session):
        raise AssertionError("Untrusted identity adapter must not be invoked")


class ExplodingGrants:
    def tenant_allowed(self, actor, tenant):
        raise AssertionError("Untrusted tenant adapter must not be invoked")

    def exact_run_allowed(self, actor, tenant, run):
        raise AssertionError("Untrusted run adapter must not be invoked")


class AuthorityBoundaryTests(unittest.TestCase):
    def test_no_provider_fails_closed(self):
        self.assertEqual(authorize_acme_view(session_id="s", tenant_id="ACME-TEST",
                         attempt_id="ACME-SIM-1234567890ABCDEF", run_id="RUN-SIM-X")["http_status"], 503)

    def test_injected_provider_cannot_grant(self):
        result = authorize_acme_view(
            session_id="s", tenant_id="ACME-TEST",
            attempt_id="ACME-SIM-1234567890ABCDEF", run_id="RUN-SIM-X",
            identity_provider=ExplodingIdentity(), grant_provider=ExplodingGrants())
        self.assertEqual(result["status"], "NO_GO")
        self.assertFalse(result["evidence_read_allowed"])
        self.assertFalse(result["autonomous_action_allowed"])

    def test_invalid_session_is_denied(self):
        result = authorize_acme_view(session_id=None, tenant_id="ACME-TEST",
                                    attempt_id="x", run_id="y",
                                    identity_provider=ExplodingIdentity(),
                                    grant_provider=ExplodingGrants())
        self.assertEqual(result["http_status"], 401)
        self.assertFalse(result["evidence_read_allowed"])


if __name__ == "__main__":
    unittest.main()
