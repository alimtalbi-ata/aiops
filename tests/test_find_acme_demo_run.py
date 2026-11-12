"""Read-only Core locator contracts; no real API or credentials used."""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location(
    "find_acme_demo_run", Path(__file__).resolve().parents[1] / "tools/find_acme_demo_run.py")
locator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(locator)
RID = "RUN-73AFC6FF9315376C"
IID = "INC-GOLDEN-P1-1edd0de6f46546e294139bf68d73d65a"


def fixture():
    run = {"run_id": RID, "incident_id": IID, "scenario_id": locator.SCENARIO,
           "mode": "DEMO", "status": "RESOLVED"}
    return {
        "/api/runs": {"items": [run]},
        f"/api/runs/{RID}": {"run": run, "events": [
            {"sequence": 1, "event_type": "RUN_CREATED", "stage": "INGEST",
             "status": "CREATED", "payload": {"scenario_id": locator.SCENARIO, "mode": "DEMO"},
             "evidence_ids": []},
            {"sequence": 2, "event_type": "EVIDENCE_ATTACHED", "stage": "ANALYZE",
             "status": "PASS", "evidence_ids": ["EVD-1", "EVD-2"]}],
            "stages": [], "gates": []},
        f"/api/noc/runs/{RID}": {"run": {k: run[k] for k in
            ("run_id", "incident_id", "mode", "status")},
            "data_classification": "SYNTHETIC_CANONICAL_RUN",
            "tenant_acl_qualified": False, "runtime_authenticated": False,
            "live_remediation_authorized": False},
        f"/api/noc/runs/{RID}/evidence-refs": {
            "schema": "aiops.core-demo-evidence-refs.v1", "run_id": RID,
            "classification": "SYNTHETIC_ONLY", "event_link_verified": True,
            "tenant_acl_qualified": False, "runtime_attested": False,
            "items": [{"evidence_id": "EVD-1", "source": "synthetic",
                       "known_at": "2026-10-29T23:00:00Z", "payload_sha256": "a" * 64}]}}


def check(data=None, url="https://core.example", token="fake-test-token", rid=RID, iid=IID):
    data = fixture() if data is None else data
    calls = []
    def get(base, path, token=None):
        calls.append((path, token))
        return copy.deepcopy(data[path])
    with mock.patch.dict(os.environ, {"AIOPS_ACME_TRUSTED_CORE_ORIGINS":
                                   "https://core.example,http://127.0.0.1:810"}):
        return locator.qualify(url, rid, iid, token, get), calls


class CoreLocatorTests(unittest.TestCase):
    def test_source_verified_only_with_exact_run_and_evidence_subset(self):
        result, calls = check()
        self.assertEqual(result["result"], "SOURCE_VERIFIED_SYNTHETIC_ONLY")
        self.assertEqual(result["authenticated_evidence_count"], 1)
        self.assertEqual(result["run_event_evidence_count"], 2)
        self.assertFalse(result["runtime_attested"])
        self.assertFalse(result["tenant_acl_qualified"])
        self.assertEqual([bool(t) for _, t in calls], [False, False, True, True])
        self.assertNotIn("fake-test-token", str(result))
        self.assertNotIn("EVD-1", str(result))

    def test_foreign_evidence_ref_unknown(self):
        data = fixture()
        data[f"/api/noc/runs/{RID}/evidence-refs"]["items"][0]["evidence_id"] = "EVD-FOREIGN"
        self.assertEqual(check(data)[0]["reason"], "EVIDENCE_EVENT_LINK_MISMATCH")

    def test_cross_run_authenticated_identity_unknown(self):
        data = fixture()
        data[f"/api/noc/runs/{RID}"]["run"]["run_id"] = "RUN-OTHER"
        self.assertEqual(check(data)[0]["reason"], "AUTH_RUN_CONTRACT_MISMATCH")

    def test_cross_run_nested_event_unknown_before_auth(self):
        data = fixture()
        data[f"/api/runs/{RID}"]["events"][1]["run_id"] = "RUN-OTHER"
        result, calls = check(data)
        self.assertEqual(result["reason"], "EVENT_EVIDENCE_REFS_UNQUALIFIED")
        self.assertEqual(len(calls), 2)

    def test_cross_run_nested_gate_unknown(self):
        data = fixture()
        data[f"/api/runs/{RID}"]["gates"] = [{"run_id": "RUN-OTHER"}]
        self.assertEqual(check(data)[0]["reason"], "NESTED_RUN_SCOPE_MISMATCH")

    def test_wrong_scenario_mode_and_incident_unknown(self):
        for field, value in (("scenario_id", "OTHER"), ("mode", "REPLAY"),
                             ("incident_id", "INC-OTHER")):
            data = fixture()
            data["/api/runs"]["items"][0][field] = value
            with self.subTest(field=field):
                self.assertEqual(check(data)[0]["reason"], "RUN_REGISTRY_MISMATCH")

    def test_invalid_creation_sequence_and_refs_unknown(self):
        for mutation in (lambda e: e[0].update(sequence=2),
                         lambda e: e[0]["payload"].update(scenario_id="OTHER"),
                         lambda e: e[1].update(evidence_ids=["../bad"]),
                         lambda e: e[1].update(evidence_ids=["EVD-1", "EVD-1"]),
                         lambda e: e[1].update(evidence_ids=[])):
            data = fixture()
            mutation(data[f"/api/runs/{RID}"]["events"])
            with self.subTest(mutation=mutation):
                self.assertEqual(check(data)[0]["reason"], "EVENT_EVIDENCE_REFS_UNQUALIFIED")

    def test_tenant_claims_and_runtime_attestation_unknown(self):
        for key, value in (("tenant_acl_qualified", True), ("runtime_attested", True)):
            data = fixture()
            data[f"/api/noc/runs/{RID}/evidence-refs"][key] = value
            with self.subTest(key=key):
                self.assertEqual(check(data)[0]["result"], "UNKNOWN")
        data = fixture()
        data[f"/api/noc/runs/{RID}/evidence-refs"]["items"][0]["tenant_id"] = "other"
        self.assertEqual(check(data)[0]["result"], "UNKNOWN")

    def test_duplicate_evidence_and_bad_metadata_unknown(self):
        for key, value in (("payload_sha256", "bad"), ("known_at", "not-time"),
                           ("source", "invalid source"), ("run_id", "RUN-OTHER")):
            data = fixture()
            data[f"/api/noc/runs/{RID}/evidence-refs"]["items"][0][key] = value
            with self.subTest(key=key):
                self.assertEqual(check(data)[0]["result"], "UNKNOWN")
        data = fixture()
        items = data[f"/api/noc/runs/{RID}/evidence-refs"]["items"]
        items.append(dict(items[0]))
        self.assertEqual(check(data)[0]["result"], "UNKNOWN")

    def test_known_at_pre_epoch_and_noncanonical_fail_closed(self):
        invalid = (
            "0001-01-01T00:00:00Z",
            "1969-12-31T23:59:59Z",
            "1970-01-01T00:30:00+01:00",
            "2026-10-29 23:00:00Z",
            "2026-10-29T23:00:00",
            "2026-10-29T23:00:00+25:00",
            "2026-10-29T23:00:00Z" + " " * 60,
        )
        for stamp in invalid:
            data = fixture()
            data[f"/api/noc/runs/{RID}/evidence-refs"]["items"][0]["known_at"] = stamp
            with self.subTest(stamp=stamp):
                result, _ = check(data)
                self.assertEqual(result["result"], "UNKNOWN")
                self.assertEqual(result["reason"], "EVIDENCE_EVENT_LINK_MISMATCH")
                self.assertIsNone(result["run_id"])

    def test_known_at_utc_epoch_boundary_is_allowed_synthetic_only(self):
        data = fixture()
        data[f"/api/noc/runs/{RID}/evidence-refs"]["items"][0]["known_at"] = (
            "1970-01-01T01:00:00+01:00"
        )
        result, _ = check(data)
        self.assertEqual(result["result"], "SOURCE_VERIFIED_SYNTHETIC_ONLY")
        self.assertFalse(result["runtime_attested"])
        self.assertFalse(result["tenant_acl_qualified"])

    def test_missing_auth_endpoint_unknown(self):
        data = fixture()
        del data[f"/api/noc/runs/{RID}/evidence-refs"]
        self.assertEqual(check(data)[0]["reason"], "CORE_AUTH_READ_FAILED")

    def test_no_token_and_unsafe_url_never_call(self):
        self.assertEqual(check(token=None)[0]["reason"], "TOKEN_NOT_CONFIGURED")
        self.assertEqual(check(url="http://core.example")[0]["reason"], "AUTH_TRANSPORT_UNSAFE")
        self.assertEqual(check(url="https://user:pass@core.example")[0]["reason"], "AUTH_TRANSPORT_UNSAFE")
        self.assertEqual(check(url="https://core.example/path")[0]["reason"], "AUTH_TRANSPORT_UNSAFE")
        self.assertEqual(check(url="http://127.0.0.1:810")[0]["result"], "SOURCE_VERIFIED_SYNTHETIC_ONLY")


    def test_explicit_pin_required_even_for_loopback(self):
        with mock.patch.dict(os.environ, {"AIOPS_ACME_TRUSTED_CORE_ORIGINS": ""}):
            for origin in ("https://core.example", "http://127.0.0.1:810"):
                with self.subTest(origin=origin):
                    self.assertEqual(locator.qualify(origin, RID, IID, "secret",
                                     get=lambda *a, **k: self.fail("network attempted"))["reason"],
                                     "AUTH_TRANSPORT_UNSAFE")

    def test_origin_pinning_blocks_authority_port_ip_and_dns_aliases(self):
        untrusted = (
            "https://evil.example", "https://core.example.evil.example",
            "https://core.example:443", "https://CORE.example",
            "https://core.example.", "https://core.example./",
            "https://core.example@evil.example",
            "https://user:pass@core.example", "https://core.example/%2e",
            "https://core.example//", "https://core.example?",
            "https://core.example#", "https://core.example/path",
            "https://core.example\\\\@evil.example",
            "https://127.0.0.2", "https://[::ffff:127.0.0.1]",
            "http://127.1:810", "http://2130706433:810",
            "http://0177.0.0.1:810", "http://127.0.0.1.evil.example:810",
            "http://localhost:810", "http://127.0.0.1:811",
            "http://core.example", "https://core.example:99999",
        )
        for origin in untrusted:
            with self.subTest(origin=origin):
                result, calls = check(url=origin)
                self.assertEqual(result["reason"], "AUTH_TRANSPORT_UNSAFE")
                self.assertEqual(calls, [])
        for origin in ("https://core.example", "https://core.example/",
                       "http://127.0.0.1:810"):
            with self.subTest(allowed=origin):
                self.assertEqual(check(url=origin)[0]["result"],
                                 "SOURCE_VERIFIED_SYNTHETIC_ONLY")

    def test_invalid_pin_entry_disables_entire_allowlist(self):
        with mock.patch.dict(os.environ, {"AIOPS_ACME_TRUSTED_CORE_ORIGINS":
                                          "https://core.example,http://evil.example"}):
            self.assertFalse(locator._safe_url("https://core.example"))
        with mock.patch.dict(os.environ, {"AIOPS_ACME_TRUSTED_CORE_ORIGINS":
                                          "https://core.example,"}):
            self.assertFalse(locator._safe_url("https://core.example"))

    def test_fetch_json_never_forwards_bearer_to_unpinned_origin(self):
        response = mock.MagicMock()
        response.status = 200
        response.read.return_value = b'{"items":[]}'
        response.__enter__.return_value = response
        with mock.patch.dict(os.environ, {"AIOPS_ACME_TRUSTED_CORE_ORIGINS":
                                          "https://core.example"}), \
             mock.patch.object(locator._OPENER, "open", return_value=response) as send:
            for origin in ("https://evil.example", "https://core.example:443",
                           "http://127.0.0.1:810", "https://127.0.0.2"):
                with self.subTest(origin=origin):
                    with self.assertRaisesRegex(ValueError, "untrusted_core_origin_or_path"):
                        locator.fetch_json(origin, "/api/runs", token="secret-test-bearer")
            send.assert_not_called()
            self.assertEqual(locator.fetch_json("https://core.example",
                                                "/api/runs", token="secret-test-bearer"),
                             {"items": []})
            send.assert_called_once()
            request = send.call_args.args[0]
            self.assertEqual(request.full_url, "https://core.example/api/runs")
            self.assertEqual(request.get_header("Authorization"), "Bearer secret-test-bearer")

    def test_fetch_json_rejects_authority_path_injection_before_network(self):
        with mock.patch.dict(os.environ, {"AIOPS_ACME_TRUSTED_CORE_ORIGINS":
                                          "https://core.example"}), \
             mock.patch.object(locator._OPENER, "open") as send:
            for path in ("@evil.example/api/runs", "//evil.example/api/runs",
                         "/api/runs?next=https://evil.example",
                         "/api/runs#evil", "/api/../runs", "/api/%2f%2fevil",
                         "/api/runs\\\\@evil.example", "https://evil.example/api/runs"):
                with self.subTest(path=path):
                    with self.assertRaises(ValueError):
                        locator.fetch_json("https://core.example", path, token="secret")
            send.assert_not_called()

    def test_network_opener_disables_proxies_and_redirects(self):
        from urllib.request import ProxyHandler
        handlers = locator._OPENER.handlers
        # urllib omits an explicitly empty ProxyHandler from the installed
        # handler list; its presence in build_opener prevents ambient proxies.
        self.assertFalse(any(isinstance(h, ProxyHandler) for h in handlers))
        self.assertTrue(any(isinstance(h, locator._NoRedirect) for h in handlers))
        for code in (301, 302, 303, 307, 308):
            self.assertIsNone(locator._NoRedirect().redirect_request(
                None, None, code, "Moved", {}, "https://evil.example"))

    def test_invalid_operator_pair_unknown(self):
        self.assertEqual(check(rid="RUN-../evil")[0]["reason"], "EXPECTED_PAIR_INVALID")
        self.assertEqual(check(iid="INC-../evil")[0]["reason"], "EXPECTED_PAIR_INVALID")

    def test_redirect_disabled(self):
        self.assertIsNone(locator._NoRedirect().redirect_request(
            None, None, 302, "Found", {}, "https://other.example"))

    def test_cli_redacts_and_fails_closed_without_token(self):
        with mock.patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": ""}), \
             mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
            code = locator.main(["--core-url", "https://core.example",
                                 "--expect-run-id", RID, "--expect-incident-id", IID,
                                 "--probe-auth-evidence"])
        self.assertEqual(code, 2)
        result = json.loads(stdout.getvalue())
        self.assertEqual(result["result"], "UNKNOWN")
        self.assertIsNone(result["run_id"])


if __name__ == "__main__":
    unittest.main()
