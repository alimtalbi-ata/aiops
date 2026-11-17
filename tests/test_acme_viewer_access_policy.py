import unittest
import hashlib
from scripts.acme_viewer_access_policy import decide_viewer_access

ATTEMPT = "ACME-SIM-" + "A" * 16
RUN = "RUN-SIM-" + hashlib.sha256(("ACME-TEST:" + ATTEMPT).encode("ascii")).hexdigest()[:24].upper()


def check(**changes):
    data = dict(authenticated_actor="operator-01",
                actor_tenants=frozenset({"ACME-TEST"}),
                requested_tenant="ACME-TEST", requested_attempt=ATTEMPT,
                requested_run=RUN, authorized_run_ids=frozenset({RUN}),
                identity_authority_qualified=True,
                run_acl_authority_qualified=True)
    data.update(changes)
    return decide_viewer_access(**data)


class ViewerPolicyTests(unittest.TestCase):
    def test_default_is_fail_closed(self):
        result = decide_viewer_access(
            authenticated_actor="operator-01", actor_tenants={"ACME-TEST"},
            requested_tenant="ACME-TEST", requested_attempt=ATTEMPT,
            requested_run=RUN, authorized_run_ids={RUN})
        self.assertEqual((result.status, result.reason),
                         (503, "TENANT_ACL_NOT_QUALIFIED"))

    def test_missing_identity_authority(self):
        self.assertEqual(check(identity_authority_qualified=False).status, 503)
        self.assertEqual(check(run_acl_authority_qualified=False).status, 503)

    def test_anonymous(self):
        self.assertEqual(check(authenticated_actor=None).status, 401)

    def test_cross_tenant(self):
        self.assertEqual(check(actor_tenants=frozenset({"OTHER"})).status, 403)
        self.assertEqual(check(requested_tenant="OTHER").status, 404)

    def test_foreign_run_is_constant_denial(self):
        self.assertEqual(check(authorized_run_ids=frozenset()).status, 404)
        self.assertEqual(check(requested_run="RUN-SIM-" + "C" * 24).status, 404)

    def test_jointly_allowed_but_wrong_attempt_run_mapping(self):
        foreign_attempt = "ACME-SIM-" + "C" * 16
        self.assertEqual(check(requested_attempt=foreign_attempt).status, 404)

    def test_truthy_nonboolean_authority_rejected(self):
        self.assertEqual(check(identity_authority_qualified=1).status, 503)
        self.assertEqual(check(run_acl_authority_qualified="true").status, 503)

    def test_untrusted_claim_shapes(self):
        self.assertEqual(check(actor_tenants=["ACME-TEST"]).status, 503)
        self.assertEqual(check(authorized_run_ids=[RUN]).status, 503)
        self.assertEqual(check(authenticated_actor="").status, 401)

    def test_valid_policy_only_not_runtime_acl(self):
        result = check()
        self.assertTrue(result.authorized)
        self.assertEqual(result.reason, "POLICY_CONDITIONS_SATISFIED_ONLY")


if __name__ == "__main__":
    unittest.main()
