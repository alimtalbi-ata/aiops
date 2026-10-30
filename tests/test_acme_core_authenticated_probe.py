"""Offline negative contracts for bearer-protected ACME evidence probe."""
import importlib.util
import io
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
import unittest
from unittest import mock

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
        result = locator.probe_authenticated_evidence("https://core.example", RID, "secret", get)
        self.assertEqual(result, {"status": "SOURCE_VERIFIED_SYNTHETIC_ONLY",
                                  "reference_count": 1, "tenant_acl_qualified": False,
                                  "runtime_attested": False})
        self.assertEqual(calls, [("/api/noc/runs/RUN-ABC123/evidence-refs", "secret")])
        self.assertNotIn("secret", str(result))
        self.assertNotIn("EVD-1", str(result))

    def test_authenticated_evidence_ids_must_appear_in_run_events(self):
        # A successful bearer GET cannot silently attach a foreign Evidence ID.
        result = locator.probe_authenticated_evidence(
            "https://core.example", RID, "secret", lambda *a, **k: response(),
            expected_event_evidence_ids=["EVD-2"])
        self.assertEqual(result, {"status": "UNKNOWN", "reason": "EVIDENCE_EVENT_LINK_MISMATCH"})

    def test_authenticated_evidence_subset_of_event_refs_is_source_only(self):
        result = locator.probe_authenticated_evidence(
            "https://core.example", RID, "secret", lambda *a, **k: response(),
            expected_event_evidence_ids=["EVD-1", "EVD-2"])
        self.assertEqual(result["status"], "SOURCE_VERIFIED_SYNTHETIC_ONLY")
        self.assertFalse(result["runtime_attested"])
        self.assertNotIn("EVD-1", str(result))

    def test_missing_or_malformed_event_refs_fail_before_authenticated_get(self):
        def get(*args, **kwargs):
            self.fail("unqualified Core event refs must not trigger a bearer read")
        for refs in ([], ["../invalid"], ["EVD-1", "EVD-1"],
                     ["EVD-1", None], "EVD-1"):
            with self.subTest(refs=refs):
                result = locator.probe_authenticated_evidence(
                    "https://core.example", RID, "secret", get,
                    expected_event_evidence_ids=refs)
                self.assertEqual(result["reason"], "EVENT_EVIDENCE_REFS_UNQUALIFIED")

    def test_main_passes_registry_event_refs_to_authenticated_probe(self):
        verified = {"result": "SOURCE_VERIFIED_REGISTRY_ONLY", "run_id": RID,
                    "evidence_refs_unattested": ["EVD-1", "EVD-2"]}
        with mock.patch.object(locator, "qualify", return_value=verified), \
             mock.patch.object(locator, "probe_authenticated_evidence",
                               return_value={"status": "SOURCE_VERIFIED_SYNTHETIC_ONLY"}) as probe, \
             mock.patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "secret"}), \
             mock.patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(locator.main(["--core-url", "https://core.example",
                                           "--portal-url", "https://portal.example",
                                           "--probe-auth-evidence"]), 0)
        self.assertEqual(probe.call_args.kwargs["expected_event_evidence_ids"],
                         ["EVD-1", "EVD-2"])

    def test_no_token_makes_no_call(self):
        def get(*args, **kwargs):
            raise AssertionError("must not call")
        self.assertEqual(locator.probe_authenticated_evidence("https://core.example", RID, "", get)["reason"], "TOKEN_NOT_CONFIGURED")

    def test_unauthorized_fails_closed(self):
        def get(*args, **kwargs):
            raise HTTPError("https://core.example", 401, "unauthorized", {}, None)
        self.assertEqual(locator.probe_authenticated_evidence("https://core.example", RID, "secret", get)["reason"], "AUTH_EVIDENCE_READ_FAILED")

    def test_missing_analysis_fails_closed(self):
        def get(*args, **kwargs):
            raise HTTPError("https://core.example", 503, "unqualified", {}, None)
        self.assertEqual(locator.probe_authenticated_evidence("https://core.example", RID, "secret", get)["status"], "UNKNOWN")

    def test_mismatched_run_fails_closed(self):
        value = response(); value["run_id"] = "RUN-OTHER"
        self.assertEqual(locator.probe_authenticated_evidence("https://core.example", RID, "secret", lambda *a, **k: value)["reason"], "EVIDENCE_CONTRACT_MISMATCH")

    def test_claimed_runtime_or_tenant_attestation_rejected(self):
        for field in ("tenant_acl_qualified", "runtime_attested"):
            value = response(); value[field] = True
            with self.subTest(field=field):
                self.assertEqual(locator.probe_authenticated_evidence("https://core.example", RID, "secret", lambda *a, **k: value)["status"], "UNKNOWN")

    def test_bad_hash_fails_closed(self):
        value = response(); value["items"][0]["payload_sha256"] = "not-a-hash"
        self.assertEqual(locator.probe_authenticated_evidence("https://core.example", RID, "secret", lambda *a, **k: value)["reason"], "EVIDENCE_CONTRACT_MISMATCH")

    def test_no_evidence_items_fails_closed(self):
        value = response(); value["items"] = []
        self.assertEqual(locator.probe_authenticated_evidence("https://core.example", RID, "secret", lambda *a, **k: value)["status"], "UNKNOWN")

    def test_nonloopback_http_rejected_before_bearer_request(self):
        def get(*args, **kwargs):
            raise AssertionError("bearer must never be sent over remote HTTP")
        result = locator.probe_authenticated_evidence(
            "http://core.example", RID, "secret", get)
        self.assertEqual(result["reason"], "AUTH_TRANSPORT_UNSAFE")

    def test_loopback_http_remains_usable_for_operator(self):
        result = locator.probe_authenticated_evidence(
            "http://127.0.0.1:810", RID, "secret",
            lambda *args, **kwargs: response())
        self.assertEqual(result["status"], "SOURCE_VERIFIED_SYNTHETIC_ONLY")

    def test_redirects_are_refused_without_forwarding_credentials(self):
        self.assertIsNone(locator._RejectRedirects().redirect_request(
            None, None, 302, "Found", {}, "https://other.example"))

    def test_main_auth_failure_is_nonzero_even_with_registry_match(self):
        verified = {"result": "SOURCE_VERIFIED_REGISTRY_ONLY", "run_id": RID}
        with mock.patch.object(locator, "qualify", return_value=verified), \
             mock.patch.object(locator, "probe_authenticated_evidence",
                               return_value={"status": "UNKNOWN", "reason": "AUTH_EVIDENCE_READ_FAILED"}), \
             mock.patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "secret"}), \
             mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            code = locator.main(["--core-url", "https://core.example",
                                 "--portal-url", "https://portal.example",
                                 "--probe-auth-evidence"])
        self.assertEqual(code, 2)
        self.assertNotIn("secret", out.getvalue())

    def test_main_auth_success_preserves_registry_only_classification(self):
        verified = {"result": "SOURCE_VERIFIED_REGISTRY_ONLY", "run_id": RID}
        with mock.patch.object(locator, "qualify", return_value=verified), \
             mock.patch.object(locator, "probe_authenticated_evidence",
                               return_value={"status": "SOURCE_VERIFIED_SYNTHETIC_ONLY"}), \
             mock.patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "secret"}), \
             mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            code = locator.main(["--core-url", "https://core.example",
                                 "--portal-url", "https://portal.example",
                                 "--probe-auth-evidence"])
        self.assertEqual(code, 0)
        self.assertIn("SOURCE_VERIFIED_REGISTRY_ONLY", out.getvalue())
        self.assertNotIn("secret", out.getvalue())

    def test_invalid_run_id_makes_no_call(self):
        def get(*args, **kwargs):
            raise AssertionError("must not call")
        self.assertEqual(locator.probe_authenticated_evidence("https://core.example", "../../escape", "secret", get)["reason"], "RUN_ID_UNQUALIFIED")


    def test_unqualified_known_at_is_unknown(self):
        for known_at in ("not-a-timestamp", "2026-10-29T23:00:00",
                         "2026-10-29T23:00:00+99:00"):
            with self.subTest(known_at=known_at):
                value = response()
                value["items"][0]["known_at"] = known_at
                result = locator.probe_authenticated_evidence(
                    "https://core.example", RID, "secret", lambda *a, **k: value)
                self.assertEqual(result["reason"], "EVIDENCE_CONTRACT_MISMATCH")

    def test_future_known_at_is_unknown(self):
        value = response()
        value["items"][0]["known_at"] = (
            datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        result = locator.probe_authenticated_evidence(
            "https://core.example", RID, "secret", lambda *a, **k: value)
        self.assertEqual(result["status"], "UNKNOWN")

    def test_bad_id_source_and_duplicate_evidence_rejected(self):
        for field, bad in (("evidence_id", "../bad"), ("source", "bad source")):
            with self.subTest(field=field):
                value = response()
                value["items"][0][field] = bad
                result = locator.probe_authenticated_evidence(
                    "https://core.example", RID, "secret", lambda *a, **k: value)
                self.assertEqual(result["reason"], "EVIDENCE_CONTRACT_MISMATCH")
        value = response()
        value["items"].append(dict(value["items"][0]))
        result = locator.probe_authenticated_evidence(
            "https://core.example", RID, "secret", lambda *a, **k: value)
        self.assertEqual(result["status"], "UNKNOWN")

    def test_evidence_item_limit_enforced(self):
        value = response()
        value["items"] = [dict(value["items"][0], evidence_id=f"EVD-{i}")
                          for i in range(81)]
        result = locator.probe_authenticated_evidence(
            "https://core.example", RID, "secret", lambda *a, **k: value)
        self.assertEqual(result["reason"], "EVIDENCE_CONTRACT_MISMATCH")

    def test_valid_zulu_timestamp_accepted(self):
        value = response()
        value["items"][0]["known_at"] = "2026-10-29T23:00:00Z"
        result = locator.probe_authenticated_evidence(
            "https://core.example", RID, "secret", lambda *a, **k: value)
        self.assertEqual(result["status"], "SOURCE_VERIFIED_SYNTHETIC_ONLY")


if __name__ == "__main__":
    unittest.main()
