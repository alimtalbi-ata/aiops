import unittest
from scripts.acme_evidence_read_seam import qualify_evidence_read
from scripts.acme_viewer_access_policy import ViewerDecision


class EvidenceReadSeamTests(unittest.TestCase):
    def test_denial_never_calls_upstream(self):
        for decision in (ViewerDecision(401, "VIEWER_UNAUTHENTICATED"),
                         ViewerDecision(403, "VIEWER_TENANT_DENIED"),
                         ViewerDecision(404, "ACME_RESOURCE_NOT_FOUND"),
                         ViewerDecision(503, "TENANT_ACL_NOT_QUALIFIED"),
                         None):
            calls = []
            def forbidden(_attempt):
                calls.append("LEAK")
                raise AssertionError("upstream called before ACL")
            result = qualify_evidence_read(decision, "ACME-SIM-" + "A" * 16,
                                           forbidden, forbidden)
            self.assertEqual(result["status"], "NO_GO")
            self.assertEqual(calls, [])

    def test_forged_positive_decision_reason_is_denied(self):
        calls = []
        def read(_attempt):
            calls.append(1)
            return {}
        result = qualify_evidence_read(ViewerDecision(200, "FORGED"),
                                       "ACME-SIM-" + "A" * 16, read, read)
        self.assertEqual(result["status"], "NO_GO")
        self.assertEqual(calls, [])

    def test_wrong_core_attempt_prevents_worker_read(self):
        calls = []
        def core(_attempt):
            calls.append("core")
            return {"attempt_id": "OTHER"}
        def worker(_attempt):
            calls.append("worker")
            return {}
        result = qualify_evidence_read(
            ViewerDecision(200, "POLICY_CONDITIONS_SATISFIED_ONLY"),
            "ACME-SIM-" + "A" * 16, core, worker)
        self.assertEqual(result["reason"], "CORE_BINDING_NOT_QUALIFIED")
        self.assertEqual(calls, ["core"])

    def test_no_data_disclosed_on_upstream_failure(self):
        def broken(_attempt):
            raise RuntimeError("secret bearer must not leak")
        result = qualify_evidence_read(
            ViewerDecision(200, "POLICY_CONDITIONS_SATISFIED_ONLY"),
            "ACME-SIM-" + "A" * 16, broken, broken)
        self.assertNotIn("secret", repr(result))
        self.assertEqual(result["reason"], "EVIDENCE_READBACK_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
