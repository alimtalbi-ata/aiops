"""Offline negative contracts for bearer-protected ACME evidence probe."""
import importlib.util
from pathlib import Path
from urllib.error import HTTPError
import unittest

spec = importlib.util.spec_from_file_location(
    "find_acme_demo_run", Path(__file__).resolve().parents[1] / "tools/find_acme_demo_run.py"
)
locator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(locator)

RID = "RUN-ABC123"


def response():
    return {"schema": "aiops.core-demo-evidence-refs.v1", "run_id": RID,
            "classification": "SYNTHETIC_ONLY", "tenant_acl_qualified": False,
            "runtime_attested": False, "event_link_verified": True,
            "items": [{"evidence_id": "EVD-1", "source": "synthetic",
                       "known_at": "2026-10-29T23:00:00+00:00", "payload_sha256": "a" * 64}]}


class AuthEvidenceProbeTests(unittest.TestCase):
    def test_auth_read_is_source_only_not_attestation(self):
        calls = []
        def get(base, path, token=None):
            calls.append((path, token))
            return response()
        result = locator.probe_authenticated_evidence("http://core", RID, "secret", get)
        self.assertEqual(result, {"status": "SOURCE_VERIFIED_SYNTHETIC_ONLY",
                                  "reference_count": 1, "tenant_acl_qualified": False,
                                  "runtime_attested": False})
        self.assertEqual(calls, [("/api/noc/runs/RUN-ABC123/evidence-refs", "secret")])
        self.assertNotIn("secret", str(result))
        self.assertNotIn("EVD-1", str(result))

    def test_no_token_makes_no_call(self):
        def get(*args, **kwargs):
            raise AssertionError("must not call")
        self.assertEqual(locator.probe_authenticated_evidence("http://core", RID, "", get)["reason"], "TOKEN_NOT_CONFIGURED")

    def test_unauthorized_fails_closed(self):
        def get(*args, **kwargs):
            raise HTTPError("http://core", 401, "unauthorized", {}, None)
        self.assertEqual(locator.probe_authenticated_evidence("http://core", RID, "secret", get)["reason"], "AUTH_EVIDENCE_READ_FAILED")

    def test_missing_analysis_fails_closed(self):
        def get(*args, **kwargs):
            raise HTTPError("http://core", 503, "unqualified", {}, None)
        self.assertEqual(locator.probe_authenticated_evidence("http://core", RID, "secret", get)["status"], "UNKNOWN")

    def test_mismatched_run_fails_closed(self):
        value = response(); value["run_id"] = "RUN-OTHER"
        self.assertEqual(locator.probe_authenticated_evidence("http://core", RID, "secret", lambda *a, **k: value)["reason"], "EVIDENCE_CONTRACT_MISMATCH")

    def test_claimed_runtime_or_tenant_attestation_rejected(self):
        for field in ("tenant_acl_qualified", "runtime_attested"):
            value = response(); value[field] = True
            with self.subTest(field=field):
                self.assertEqual(locator.probe_authenticated_evidence("http://core", RID, "secret", lambda *a, **k: value)["status"], "UNKNOWN")

    def test_bad_hash_fails_closed(self):
        value = response(); value["items"][0]["payload_sha256"] = "not-a-hash"
        self.assertEqual(locator.probe_authenticated_evidence("http://core", RID, "secret", lambda *a, **k: value)["reason"], "EVIDENCE_CONTRACT_MISMATCH")

    def test_no_evidence_items_fails_closed(self):
        value = response(); value["items"] = []
        self.assertEqual(locator.probe_authenticated_evidence("http://core", RID, "secret", lambda *a, **k: value)["status"], "UNKNOWN")

    def test_invalid_run_id_makes_no_call(self):
        def get(*args, **kwargs):
            raise AssertionError("must not call")
        self.assertEqual(locator.probe_authenticated_evidence("http://core", "../../escape", "secret", get)["reason"], "RUN_ID_UNQUALIFIED")


if __name__ == "__main__":
    unittest.main()
