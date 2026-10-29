"""Real Core HTTP + PostgreSQL integration for the DEMO Policy observation.

CI-only synthetic rows in an ephemeral database; no mocks, Temporal, LIVE
command, tenant runtime authorization, or production connection.
"""
import os
import unittest

import psycopg
import requests
from psycopg.types.json import Jsonb

BASE = "http://127.0.0.1:1810"
TOKEN = os.environ["AIOPS_INTERNAL_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]
PREFIX = "CI-DEMO-POLICY-"


class DemoPolicyCoreRealIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {
            "BLOCKED": ("DEMO", "BLOCKED", True, {}, None),
            "RESOLVED": ("DEMO", "RESOLVED", True, {}, ("PASS", "SIMULATE")),
            "RUNNING": ("DEMO", "RUNNING", True, {}, None),
            "RESOLVED-NOGATE": ("DEMO", "RESOLVED", True, {}, None),
            "UNKNOWN-GATE": ("DEMO", "BLOCKED", True, {}, ("UNKNOWN", "HUMAN_APPROVAL")),
            "FORGED-GATE": ("DEMO", "RESOLVED", True, {}, ("PASS", "ALLOW")),
            "GATE-BEFORE-RUN": ("DEMO", "RESOLVED", True, {}, ("PASS", "SIMULATE")),
            "GATE-IN-FUTURE": ("DEMO", "RESOLVED", True, {}, ("PASS", "SIMULATE")),
            "RUN-IN-FUTURE": ("DEMO", "RUNNING", True, {}, None),
            "LIVE": ("LIVE", "RESOLVED", True, {}, None),
            "OBSERVED": ("DEMO", "RESOLVED", False, {}, None),
            "TENANT": ("DEMO", "BLOCKED", True,
                       {"metadata": {"ownerTenantId": "PRIVATE-CI-TENANT"}}, None),
        }
        with psycopg.connect(DATABASE_URL) as c:
            for suffix, (mode, status, synthetic, payload, gate) in cls.cases.items():
                rid, iid = "RUN-" + PREFIX + suffix, "INC-" + PREFIX + suffix
                c.execute(
                    "insert into aiops.incidents(incident_id,external_id,title,severity,"
                    "state,opened_at,source,synthetic,payload) "
                    "values(%s,%s,'Ephemeral CI synthetic observation','P1',"
                    "'OPEN',now(),'ci',%s,%s)",
                    (iid, PREFIX + suffix, synthetic, Jsonb(payload)),
                )
                c.execute(
                    "insert into aiops.runs(run_id,incident_id,mode,scenario_id,"
                    "status,idempotency_key) values(%s,%s,%s,'CI-ACME',%s,%s)",
                    (rid, iid, mode, status, PREFIX + suffix.lower()),
                )
                if gate:
                    c.execute(
                        "insert into aiops.gates(gate_id,run_id,stage,state,decision,reason)"
                        " values(%s,%s,'POLICY',%s,%s,'ephemeral CI record')",
                        ("GATE-" + PREFIX + suffix, rid, gate[0], gate[1]),
                    )
            c.execute(
                "update aiops.gates set evaluated_at = "
                "(select created_at - interval '1 second' from aiops.runs "
                "where run_id=%s) where run_id=%s",
                ("RUN-" + PREFIX + "GATE-BEFORE-RUN",
                 "RUN-" + PREFIX + "GATE-BEFORE-RUN"),
            )
            c.execute(
                "update aiops.gates set evaluated_at = now() + interval '1 day' "
                "where run_id=%s",
                ("RUN-" + PREFIX + "GATE-IN-FUTURE",),
            )
            c.execute(
                "update aiops.runs set created_at = now() + interval '1 day' "
                "where run_id=%s",
                ("RUN-" + PREFIX + "RUN-IN-FUTURE",),
            )

    @classmethod
    def tearDownClass(cls):
        with psycopg.connect(DATABASE_URL) as c:
            c.execute("delete from aiops.gates where run_id like %s", ("RUN-" + PREFIX + "%",))
            c.execute("delete from aiops.runs where run_id like %s", ("RUN-" + PREFIX + "%",))
            c.execute("delete from aiops.incidents where incident_id like %s",
                      ("INC-" + PREFIX + "%",))

    def read(self, suffix, token=TOKEN):
        headers = {} if token is None else {"Authorization": "Bearer " + token}
        return requests.get(BASE + "/api/noc/runs/RUN-" + PREFIX + suffix +
                            "/policy-status", headers=headers, timeout=3,
                            allow_redirects=False)

    def test_resolved_with_recorded_simulate_is_never_live_proof(self):
        response = self.read("RESOLVED")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        data = response.json()
        self.assertEqual(data["schema"], "aiops.core-demo-policy-observation.v1")
        self.assertEqual(data["run_id"], "RUN-" + PREFIX + "RESOLVED")
        self.assertEqual(data["incident_id"], "INC-" + PREFIX + "RESOLVED")
        self.assertEqual(data["run_status"], "RESOLVED")
        self.assertEqual((data["policy_gate_state"], data["policy_decision"]),
                         ("PASS", "SIMULATE"))
        self.assertEqual(data["explanation_code"], "RESOLVED_WITH_SIMULATE_GATE_NOT_LIVE")
        self.assertTrue(data["policy_gate_recorded"])
        for key in ("runtime_attested", "policy_http_verified", "hitl_approval_verified",
                    "temporal_execution_verified", "postchecks_verified",
                    "rollback_verified", "tenant_acl_qualified",
                    "live_remediation_authorized"):
            self.assertIs(data[key], False, key)
        self.assertNotIn("ephemeral CI record", response.text)

    def test_blocked_without_gate_is_missing_not_causal_explanation(self):
        response = self.read("BLOCKED")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["run_status"], "BLOCKED")
        self.assertEqual(data["policy_gate_state"], "MISSING")
        self.assertIsNone(data["policy_decision"])
        self.assertIs(data["policy_gate_recorded"], False)
        self.assertEqual(data["explanation_code"], "BLOCKED_WITHOUT_POLICY_GATE")

    def test_running_and_resolved_without_gate_remain_unverified(self):
        for suffix, code in (
            ("RUNNING", "RUNNING_NO_TERMINAL_PROOF"),
            ("RESOLVED-NOGATE", "RESOLVED_POLICY_SIMULATION_UNVERIFIED"),
        ):
            with self.subTest(suffix=suffix):
                response = self.read(suffix)
                self.assertEqual(response.status_code, 200, response.text)
                data = response.json()
                self.assertEqual(data["explanation_code"], code)
                self.assertEqual(data["policy_gate_state"], "MISSING")
                self.assertIs(data["temporal_execution_verified"], False)

    def test_persisted_unknown_gate_does_not_become_simulate(self):
        response = self.read("UNKNOWN-GATE")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["policy_gate_state"], "UNKNOWN")
        self.assertEqual(data["policy_decision"], "HUMAN_APPROVAL")
        self.assertEqual(data["explanation_code"], "BLOCKED_CAUSE_NOT_ESTABLISHED")
        self.assertIs(data["live_remediation_authorized"], False)

    def test_inconsistent_gate_is_rejected_even_when_run_is_resolved(self):
        response = self.read("FORGED-GATE")
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json(), {"detail": "demo_policy_observation_unavailable"})
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertNotIn("ALLOW", response.text)

    def test_impossible_run_or_gate_chronology_is_rejected(self):
        # Actual Core HTTP and PostgreSQL timestamptz, not a mock Policy server.
        for suffix in ("GATE-BEFORE-RUN", "GATE-IN-FUTURE", "RUN-IN-FUTURE"):
            with self.subTest(suffix=suffix):
                response = self.read(suffix)
                self.assertEqual(response.status_code, 503, response.text)
                self.assertEqual(response.json(),
                                 {"detail": "demo_policy_observation_unavailable"})
                self.assertEqual(response.headers["cache-control"], "no-store")
                self.assertNotIn("SIMULATE", response.text)
                self.assertNotIn("RUN-" + PREFIX, response.text)

    def test_live_observed_tenant_and_missing_run_are_denied(self):
        for suffix in ("LIVE", "OBSERVED", "TENANT", "MISSING", "BAD!ID"):
            with self.subTest(suffix=suffix):
                response = self.read(suffix)
                self.assertEqual(response.status_code, 503, response.text)
                self.assertEqual(response.headers["cache-control"], "no-store")
                self.assertNotIn("PRIVATE-CI-TENANT", response.text)
                self.assertNotIn("RUN-" + PREFIX, response.text)

    def test_missing_and_forged_bearer_are_rejected(self):
        for token in (None, "", "invalid", TOKEN + " extra"):
            with self.subTest(token=repr(token)):
                response = self.read("RESOLVED", token=token)
                self.assertEqual(response.status_code, 401, response.text)
                self.assertEqual(response.headers["www-authenticate"], "Bearer")
                self.assertEqual(response.headers["cache-control"], "no-store")
                self.assertNotIn("RUN-" + PREFIX, response.text)



    def test_readonly_probe_observes_real_core_http_without_e2e_claim(self):
        # This calls actual ephemeral Core HTTP backed by PostgreSQL, not a mock.
        from scripts.probe_demo_policy_readonly import probe
        for suffix, status, gate in (
            ("BLOCKED", "BLOCKED", "MISSING"),
            ("RESOLVED", "RESOLVED", "PASS"),
            ("RUNNING", "RUNNING", "MISSING"),
        ):
            with self.subTest(suffix=suffix):
                rid = "RUN-" + PREFIX + suffix
                iid = "INC-" + PREFIX + suffix
                result = probe(BASE, rid, iid, TOKEN)
                self.assertEqual(result["overall"], "NO_GO")
                self.assertEqual(result["observation_status"],
                                 "CORE_READ_OBSERVED_NOT_E2E")
                self.assertEqual((result["run_id"], result["incident_id"]),
                                 (rid, iid))
                self.assertEqual((result["run_status"], result["policy_gate_state"]),
                                 (status, gate))
                self.assertIs(result["runtime_attested"], False)
                self.assertIs(result["live_remediation_authorized"], False)
                self.assertNotIn(TOKEN, str(result))

    def test_readonly_probe_rejects_wrong_ids_auth_and_core_refusals(self):
        from scripts.probe_demo_policy_readonly import ProbeError, probe
        rid, iid = "RUN-" + PREFIX + "RESOLVED", "INC-" + PREFIX + "RESOLVED"
        for run, incident, token in (
            (rid, iid + "-WRONG", TOKEN),
            (rid, iid, "invalid-token"),
            (rid, iid, ""),
            ("RUN-" + PREFIX + "LIVE", "INC-" + PREFIX + "LIVE", TOKEN),
            ("RUN-" + PREFIX + "FORGED-GATE",
             "INC-" + PREFIX + "FORGED-GATE", TOKEN),
            ("RUN-" + PREFIX + "GATE-IN-FUTURE",
             "INC-" + PREFIX + "GATE-IN-FUTURE", TOKEN),
        ):
            with self.subTest(run=run, incident=incident):
                with self.assertRaises(ProbeError):
                    probe(BASE, run, incident, token)

    def test_readonly_probe_strict_json_accepts_real_core_and_rejects_ambiguity(self):
        # Positive is the real ephemeral Core HTTP/PostgreSQL response.
        # Malformed payloads below test the parser only, not a fake service.
        from scripts.probe_demo_policy_readonly import ProbeError, decode_core_json
        response = self.read("RESOLVED")
        self.assertEqual(response.status_code, 200, response.text)
        raw = response.content
        self.assertEqual(decode_core_json(raw), response.json())
        self.assertTrue(raw.startswith(b"{"))
        for name, payload in (
            ("top_level_duplicate", b'{"run_id":"RUN-FORGED",' + raw[1:]),
            ("nested_duplicate", b'{"nested":{"state":"PASS","state":"ALLOW"}}'),
            ("nan", b'{"run_status":NaN}'),
            ("infinity", b'{"run_status":Infinity}'),
            ("negative_infinity", b'{"run_status":-Infinity}'),
            ("malformed", b'{"run_status":'),
        ):
            with self.subTest(case=name):
                with self.assertRaises(ProbeError):
                    decode_core_json(payload)

    def test_readonly_probe_rejects_non_utf8_and_conflicting_http_headers(self):
        # Real Core/PostgreSQL positive; malformed bytes and header fixtures are
        # parser-only negatives, not simulated application integration.
        from email.message import Message
        from scripts.probe_demo_policy_readonly import (
            ProbeError, decode_core_json, validate_core_headers,
        )
        response = self.read("RESOLVED")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(decode_core_json(response.content), response.json())
        for name, payload in (
            ("utf8_bom", b"\xef\xbb\xbf" + response.content),
            ("utf16_le", response.text.encode("utf-16-le")),
            ("utf16_be", response.text.encode("utf-16-be")),
            ("utf32_le", response.text.encode("utf-32-le")),
            ("invalid_utf8", b'{"run_id":"\xff"}'),
        ):
            with self.subTest(encoding=name):
                with self.assertRaises(ProbeError):
                    decode_core_json(payload)

        def headers():
            h = Message()
            h["Cache-Control"] = "private, no-store"
            h["Content-Type"] = "application/json; charset=UTF-8"
            return h

        validate_core_headers(headers())
        for name in (
            "duplicate_cache", "duplicate_media", "gzip", "utf16_charset",
            "missing_no_store", "wrong_media",
        ):
            with self.subTest(headers=name):
                h = headers()
                if name == "duplicate_cache":
                    h["Cache-Control"] = "public"
                elif name == "duplicate_media":
                    h["Content-Type"] = "text/plain"
                elif name == "gzip":
                    h["Content-Encoding"] = "gzip"
                elif name == "utf16_charset":
                    h.replace_header("Content-Type", "application/json; charset=utf-16")
                elif name == "missing_no_store":
                    h.replace_header("Cache-Control", "public, max-age=3600")
                elif name == "wrong_media":
                    h.replace_header("Content-Type", "text/html")
                with self.assertRaises(ProbeError):
                    validate_core_headers(h)

    def test_readonly_probe_contract_rejects_forged_attestations_and_addresses(self):
        from scripts.probe_demo_policy_readonly import (
            ProbeError, loopback_url, validate_observation,
        )
        rid, iid = "RUN-" + PREFIX + "RESOLVED", "INC-" + PREFIX + "RESOLVED"
        source = self.read("RESOLVED").json()
        for field, value in (
            ("runtime_attested", True),
            ("tenant_acl_qualified", True),
            ("live_remediation_authorized", True),
            ("mode", "LIVE"),
            ("incident_id", "INC-OTHER"),
            ("policy_decision", "ALLOW"),
            ("explanation_code", "LIVE_REMEDIATED"),
            ("provenance", "LIVE_ATTESTED"),
            ("run_status", []),
            ("policy_gate_state", []),
        ):
            with self.subTest(field=field):
                forged = dict(source)
                forged[field] = value
                with self.assertRaises(ProbeError):
                    validate_observation(forged, rid, iid)
        for url in (
            "http://10.79.94.202:1810", "http://localhost:1810",
            "https://127.0.0.1:1810", "http://127.0.0.1:1810/api",
            "http://user:pass@127.0.0.1:1810",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ProbeError):
                    loopback_url(url)

    def test_real_policy_http_core_values_match_but_never_attest_run_binding(self):
        # Both HTTP services and PostgreSQL 16 are real and ephemeral in CI.
        # The Core gate fixture is seeded independently of Policy: no causality.
        from scripts.probe_demo_policy_readonly import (
            ProbeError, compare_unbound_policy_values,
        )
        payload = {
            "mode": "DEMO", "command": "OBSERVE", "severity": "P2",
            "confidence": 0.99, "evidence_count": 2,
            "critic_validated": True, "redundancy_ok": True,
            "evidence_fresh": True, "preconditions_verified": True,
            "fencing_verified": True, "human_approved": False,
        }
        policy_http = requests.post(
            "http://127.0.0.1:1813/api/policy/check",
            json=payload, timeout=3, allow_redirects=False,
        )
        self.assertEqual(policy_http.status_code, 200, policy_http.text)
        self.assertEqual(
            (policy_http.json()["state"], policy_http.json()["decision"]),
            ("PASS", "SIMULATE"),
        )
        rid = "RUN-" + PREFIX + "RESOLVED"
        iid = "INC-" + PREFIX + "RESOLVED"
        core_http = self.read("RESOLVED")
        self.assertEqual(core_http.status_code, 200, core_http.text)
        comparison = compare_unbound_policy_values(
            core_http.json(), policy_http.json(), rid, iid,
        )
        self.assertEqual(comparison["overall"], "NO_GO")
        self.assertEqual(comparison["comparison"], "VALUES_MATCH_NOT_CAUSAL_PROOF")
        self.assertIs(comparison["policy_run_binding_verified"], False)
        self.assertIs(comparison["live_remediation_authorized"], False)
        self.assertNotIn("reason", comparison)

        # Matching a fresh Policy response must never fabricate a missing gate.
        for suffix in ("RESOLVED-NOGATE", "BLOCKED", "RUNNING"):
            with self.subTest(missing_gate=suffix):
                core = self.read(suffix)
                self.assertEqual(core.status_code, 200, core.text)
                with self.assertRaises(ProbeError):
                    compare_unbound_policy_values(
                        core.json(), policy_http.json(),
                        "RUN-" + PREFIX + suffix, "INC-" + PREFIX + suffix,
                    )
        with self.assertRaises(ProbeError):
            compare_unbound_policy_values(
                core_http.json(), policy_http.json(), rid, iid + "-OTHER",
            )
        with self.assertRaises(ProbeError):
            compare_unbound_policy_values(
                core_http.json(), {**policy_http.json(), "decision": "ALLOW"},
                rid, iid,
            )
        with self.assertRaises(ProbeError):
            compare_unbound_policy_values(
                core_http.json(), {**policy_http.json(), "run_id": rid},
                rid, iid,
            )
        for invalid in ([], True, None):
            with self.subTest(malformed_policy=repr(invalid)):
                with self.assertRaises(ProbeError):
                    compare_unbound_policy_values(
                        core_http.json(), {**policy_http.json(), "state": invalid},
                        rid, iid,
                    )

        # No Evidence: Policy UNKNOWN is compatible with an independently
        # persisted UNKNOWN gate, but still NOT a verified HITL approval.
        unknown = requests.post(
            "http://127.0.0.1:1813/api/policy/check",
            json={**payload, "evidence_count": 0},
            timeout=3, allow_redirects=False,
        )
        self.assertEqual(unknown.status_code, 200, unknown.text)
        unknown_core = self.read("UNKNOWN-GATE")
        self.assertEqual(unknown_core.status_code, 200, unknown_core.text)
        report = compare_unbound_policy_values(
            unknown_core.json(), unknown.json(),
            "RUN-" + PREFIX + "UNKNOWN-GATE",
            "INC-" + PREFIX + "UNKNOWN-GATE",
        )
        self.assertEqual(
            (report["policy_gate_state"], report["policy_decision"]),
            ("UNKNOWN", "HUMAN_APPROVAL"),
        )
        self.assertIs(report["hitl_approval_verified"], False)

        live = requests.post(
            "http://127.0.0.1:1813/api/policy/check",
            json={**payload, "mode": "LIVE", "severity": "P1",
                  "command": "REMEDIATE", "human_approved": True},
            timeout=3, allow_redirects=False,
        )
        self.assertEqual(live.status_code, 200, live.text)
        self.assertEqual(
            (live.json()["state"], live.json()["decision"]),
            ("BLOCKED", "ESCALATE"),
        )
        self.assertEqual(self.read("LIVE").status_code, 503)
        with self.assertRaises(ProbeError):
            compare_unbound_policy_values(
                core_http.json(), live.json(), rid, iid,
            )

if __name__ == "__main__":
    unittest.main()
