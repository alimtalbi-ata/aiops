"""Real Twin HTTP container + PostgreSQL 16 seed integration, never a LIVE proof.

Only runs in quality.yml with ephemeral services and CI-only credentials.
No mocks, no production network, no mutation of the seeded topology.
"""
import copy
from email.message import Message
import json
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

from scripts.qualify_acme_twin_readonly import (QualificationError, decode_impact_json,
                                                qualify, loopback_base, validate_impact,
                                                validate_twin_http_headers)

import psycopg
import requests

BASE = os.environ["AIOPS_TWIN_CI_URL"]
TOKEN = os.environ["AIOPS_TWIN_CI_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]


class TwinImpactRealIntegration(unittest.TestCase):
    def read(self, node_id, token=TOKEN):
        headers = {} if token is None else {"Authorization": "Bearer " + token}
        return requests.get(
            BASE + "/api/twin/impact/" + node_id,
            headers=headers, timeout=5, allow_redirects=False,
        )

    def test_prometheus_metrics_only_accept_dedicated_scrape_identity(self):
        metrics_url = BASE + "/metrics"
        def scrape(token=None):
            headers = {} if token is None else {"Authorization": "Bearer " + token}
            return requests.get(metrics_url, headers=headers, timeout=5, allow_redirects=False)
        for token in (None, TOKEN, os.environ["AIOPS_INTERNAL_TOKEN"], "invalid"):
            with self.subTest(identity="anonymous" if token is None else "non-metrics"):
                self.assertEqual(scrape(token).status_code, 401)
        response = scrape("ci-twin-metrics-ephemeral-only")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.headers["content-type"].startswith("text/plain"))
        self.assertIn("aiops_twin_nodes 25\\n", response.text)
        self.assertNotIn("ACME-BIZ-PAYMENTS", response.text)
        # Metrics token cannot read topology or mutate synthetic events.
        self.assertEqual(self.read("ACME-SAN-FABRIC-A", "ci-twin-metrics-ephemeral-only").status_code, 401)
        self.assertEqual(requests.post(BASE + "/api/twin/synthetic-event",
            json={"action":"OBSERVE","target_node_id":"ACME-SAN-FABRIC-A","run_id":"CI-METRICS"},
            headers={"Authorization":"Bearer ci-twin-metrics-ephemeral-only"},
            timeout=5).status_code, 401)

    def test_ephemeral_seed_is_25_nodes_and_23_directed_edges(self):
        with psycopg.connect(DATABASE_URL) as c:
            self.assertEqual(c.execute("select count(*) from aiops.twin_nodes").fetchone()[0], 25)
            self.assertEqual(c.execute("select count(*) from aiops.twin_edges").fetchone()[0], 23)
            self.assertEqual(
                c.execute(
                    "select source_id,target_id from aiops.twin_edges "
                    "where edge_id='ACME-E08'"
                ).fetchone(),
                ("ACME-STO-PURE01", "ACME-SAN-FABRIC-A"),
            )

    def test_san_fabric_a_reaches_only_real_dependent_consumers(self):
        response = self.read("ACME-SAN-FABRIC-A")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers.get("cache-control"), "no-store")
        data = response.json()
        expected = {
            "ACME-SAN-FABRIC-A": 0,
            "ACME-STO-PURE01": 1,
            "ACME-STO-POWERMAX01": 1,
            "ACME-VM-PAY01": 2,
            "ACME-VM-PAY02": 2,
            "ACME-APP-ERP": 2,
            "ACME-APP-ORACLEPAY": 3,
            "ACME-SVC-ERP": 3,
            "ACME-SVC-PAYMENTS": 4,
            "ACME-BIZ-PAYMENTS": 5,
        }
        self.assertEqual(
            {item["node_id"]: item["depth"] for item in data["affected"]},
            expected,
        )
        # Every path edge is a real row in the seeded PostgreSQL graph.
        # No synthetic SAN -> host shortcut may be emitted.
        edges = data["shortest_path_edges"]
        self.assertEqual(
            [edge["edge_id"] for edge in edges],
            ["ACME-E01", "ACME-E02", "ACME-E04", "ACME-E05",
             "ACME-E06", "ACME-E07", "ACME-E08", "ACME-E14",
             "ACME-E15", "ACME-E16"],
        )
        self.assertEqual(
            data["path_semantics"],
            "SEEDED_TOPOLOGY_SHORTEST_HOPS_NOT_RUNTIME_CAUSALITY",
        )
        with psycopg.connect(DATABASE_URL) as c:
            actual = {
                row[0]: row[1:]
                for row in c.execute(
                    "select edge_id,source_id,target_id,relation_type "
                    "from aiops.twin_edges"
                ).fetchall()
            }
        for edge in edges:
            with self.subTest(edge=edge["edge_id"]):
                self.assertEqual(
                    (edge["source_id"], edge["target_id"], edge["relation_type"]),
                    actual[edge["edge_id"]],
                )
                self.assertEqual(
                    expected[edge["source_id"]],
                    expected[edge["target_id"]] + 1,
                )
        self.assertNotIn("ACME-E10", {e["edge_id"] for e in edges})
        self.assertNotIn("ACME-E09", {e["edge_id"] for e in edges})
        self.assertEqual(data["traversal_direction"], "REVERSE_CONSUMER_TO_DEPENDENCY")
        self.assertEqual(data["affected_semantics"], "DEPENDENT_CANDIDATES_NOT_CONFIRMED_IMPACT")
        self.assertEqual(data["runtime_impact_state"], "UNKNOWN")
        self.assertIs(data["runtime_authenticated"], False)
        self.assertIs(data["tenant_acl_qualified"], False)
        self.assertIs(data["redundancy_evaluated"], False)
        self.assertIs(data["live_remediation_authorized"], False)
        # SAN-B is a sibling path, while RHEL01 is a VM dependency, not a SAN consumer.
        returned = {item["node_id"] for item in data["affected"]}
        self.assertNotIn("ACME-SAN-FABRIC-B", returned)
        self.assertNotIn("ACME-SRV-RHEL01", returned)
        self.assertNotIn("ACME-APP-PORTAL", returned)
        self.assertEqual(response.json(), self.read("ACME-SAN-FABRIC-A").json())

    def test_direction_is_not_inverted_or_invented(self):
        # Business node depends on the service; it has no dependent consumers.
        r = self.read("ACME-BIZ-PAYMENTS")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(
            [(item["node_id"], item["depth"]) for item in r.json()["affected"]],
            [("ACME-BIZ-PAYMENTS", 0)],
        )
        self.assertEqual(r.json()["shortest_path_edges"], [])

    def test_all_twin_read_surfaces_reject_anonymous_and_wrong_token(self):
        # Real Twin HTTP + PostgreSQL 16: no unauthenticated topology or metrics.
        paths = (
            '/api/twin/summary', '/api/twin/nodes', '/api/twin/graph',
            '/api/twin/at?known_at=2026-10-28T00:00:00Z', '/metrics',
        )
        for path in paths:
            for token in (None, 'invalid', TOKEN + '-extra'):
                with self.subTest(path=path, token=token):
                    headers = {} if token is None else {'Authorization': 'Bearer ' + token}
                    response = requests.get(BASE + path, headers=headers, timeout=5,
                                            allow_redirects=False)
                    self.assertEqual(response.status_code, 401, response.text)
                    self.assertEqual(response.headers.get('cache-control'), 'no-store')
                    self.assertEqual(response.headers.get('www-authenticate'), 'Bearer')
                    self.assertNotIn('ACME-SAN-FABRIC-A', response.text)
                    self.assertNotIn('aiops_twin_nodes', response.text)
            with self.subTest(path=path, token='valid'):
                response = requests.get(BASE + path,
                                        headers={'Authorization': 'Bearer ' + TOKEN},
                                        timeout=5, allow_redirects=False)
                self.assertEqual(response.status_code, 200, response.text[:200])
        self.assertEqual(requests.get(BASE + '/health', timeout=5).status_code, 200)

    def test_distinct_internal_identity_reads_but_cannot_write_synthetic_events(self):
        # Real Twin HTTP + ephemeral PostgreSQL: Portal/Copilot use the internal
        # service token, not necessarily the Twin administrator token.
        internal = os.environ["AIOPS_INTERNAL_TOKEN"]
        self.assertNotEqual(internal, TOKEN)
        for path in ("/api/twin/summary", "/api/twin/impact/ACME-SAN-FABRIC-A",
                     "/api/twin/graph", "/metrics"):
            with self.subTest(path=path):
                response = requests.get(
                    BASE + path, headers={"Authorization": "Bearer " + internal},
                    timeout=5, allow_redirects=False,
                )
                self.assertEqual(response.status_code, 200, response.text[:200])
        denied = requests.post(
            BASE + "/api/twin/synthetic-event",
            json={"action": "OBSERVE", "target_node_id": "ACME-SAN-FABRIC-A",
                  "run_id": "CI-SYNTHETIC-DENIAL"},
            headers={"Authorization": "Bearer " + internal},
            timeout=5, allow_redirects=False,
        )
        self.assertEqual(denied.status_code, 401, denied.text)
        # Even a valid internal service credential must not grant write authority.
        with psycopg.connect(DATABASE_URL) as c:
            count = c.execute(
                "select count(*) from aiops.observations "
                "where payload::text like '%CI-SYNTHETIC-DENIAL%'"
            ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_unknown_node_and_missing_auth_fail_closed(self):
        for token in (None, "", "incorrect", TOKEN + "-extra"):
            with self.subTest(token=token):
                r = self.read("ACME-SAN-FABRIC-A", token)
                self.assertEqual(r.status_code, 401, r.text)
                self.assertEqual(r.headers.get("cache-control"), "no-store")
                self.assertNotIn("ACME-STO-PURE01", r.text)
                self.assertNotIn("shortest_path_edges", r.text)
        r = self.read("ACME-NODE-NOT-SEEDED")
        self.assertEqual(r.status_code, 404, r.text)
        self.assertEqual(r.headers.get("cache-control"), "no-store")
        self.assertNotIn("ACME-SVC-PAYMENTS", r.text)


    def test_readonly_qualification_against_real_twin_and_cli(self):
        result = qualify(BASE, TOKEN)
        self.assertEqual(result["contract_status"], "PASS")
        self.assertEqual(result["overall"], "NO_GO")
        self.assertEqual(result["provenance"], "SIMULATED_TOPOLOGY_NOT_RUNTIME_IMPACT")
        self.assertEqual(result["path_edge_ids"],
                         ["ACME-E08", "ACME-E06", "ACME-E04", "ACME-E02", "ACME-E01"])
        self.assertIs(result["san_host_link_verified"], False)
        self.assertEqual(result["runtime_impact_state"], "UNKNOWN")
        self.assertIn("TENANT_RBAC_NOT_QUALIFIED", result["blockers"])
        self.assertIn("DEPLOY_COVERAGE_AND_ROLLBACK_NOT_QUALIFIED", result["blockers"])
        process = subprocess.run(
            [sys.executable, "scripts/qualify_acme_twin_readonly.py",
             "--base-url", BASE],
            env={**os.environ, "AIOPS_TWIN_READ_TOKEN": TOKEN},
            text=True, capture_output=True, timeout=15, check=False,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout), result)

    def test_strict_twin_json_refuses_ambiguous_or_nonfinite_http_payloads(self):
        # Positive is the actual Twin HTTP response from ephemeral PostgreSQL,
        # not a mocked integration. Negative variants are hostile byte payloads.
        response = self.read("ACME-SAN-FABRIC-A")
        self.assertEqual(response.status_code, 200, response.text)
        original = response.content
        self.assertEqual(validate_impact(decode_impact_json(original))["overall"],
                         "NO_GO")
        variants = (
            ("duplicate_root", b'{"root":"FORGED",' + original[1:],
             "duplicate_twin_json_key"),
            ("duplicate_nested_edge",
             original.replace(b'"edge_id":', b'"edge_id":"FORGED","edge_id":', 1),
             "duplicate_twin_json_key"),
            ("nan", b'{"untrusted":NaN,' + original[1:], "nonfinite_twin_json"),
            ("infinity", b'{"untrusted":Infinity,' + original[1:],
             "nonfinite_twin_json"),
            ("negative_infinity", b'{"untrusted":-Infinity,' + original[1:],
             "nonfinite_twin_json"),
            ("overflow_exponent", b'{"untrusted":1e999,' + original[1:],
             "nonfinite_twin_json"),
            ("invalid_utf8", original + b'\xff', "invalid_json"),
            ("truncated", original[:-1], "invalid_json"),
            ("too_deep", b"[" * 1200 + b"]" * 1200,
             "excessive_twin_json_nesting"),
        )
        for name, raw, expected in variants:
            with self.subTest(case=name):
                with self.assertRaises(QualificationError) as ctx:
                    decode_impact_json(raw)
                self.assertEqual(str(ctx.exception), expected)

    def test_twin_qualifier_rejects_ambiguous_http_metadata(self):
        # Both baseline responses come from the real Twin/PostgreSQL CI stack.
        # Mutated headers are adversarial unit inputs, not claimed HTTP E2E.
        for anonymous in (False, True):
            response = self.read("ACME-SAN-FABRIC-A",
                                 token=None if anonymous else TOKEN)
            self.assertEqual(response.status_code, 401 if anonymous else 200)
            original = Message()
            for name, value in response.headers.items():
                original[name] = value
            validate_twin_http_headers(original, anonymous=anonymous)

            cases = [
                ("missing_cache", "Cache-Control", [], "missing_no_store"),
                ("duplicate_cache", "Cache-Control", ["no-store", "public"],
                 "missing_no_store"),
                ("duplicate_media", "Content-Type",
                 ["application/json", "text/plain"], "invalid_content_type"),
                ("utf16_media", "Content-Type",
                 ["application/json; charset=utf-16"], "invalid_content_type"),
                ("gzip", "Content-Encoding", ["gzip"], "invalid_content_encoding"),
                ("duplicate_identity", "Content-Encoding",
                 ["identity", "identity"], "invalid_content_encoding"),
                ("chunked", "Transfer-Encoding", ["chunked"],
                 "invalid_transfer_encoding"),
                ("duplicate_length", "Content-Length", ["2", "3"],
                 "invalid_content_length"),
                ("bad_length", "Content-Length", ["NaN"],
                 "invalid_content_length"),
                ("huge_length", "Content-Length", ["9" * 5000],
                 "invalid_content_length"),
            ]
            if anonymous:
                cases += [
                    ("missing_challenge", "WWW-Authenticate", [],
                     "invalid_anonymous_denial"),
                    ("duplicate_challenge", "WWW-Authenticate",
                     ["Bearer", "Basic"], "invalid_anonymous_denial"),
                ]
            else:
                cases += [
                    ("missing_nosniff", "X-Content-Type-Options", [],
                     "missing_nosniff"),
                    ("duplicate_nosniff", "X-Content-Type-Options",
                     ["nosniff", "nosniff"], "missing_nosniff"),
                    ("unexpected_challenge", "WWW-Authenticate", ["Bearer"],
                     "unexpected_auth_challenge"),
                ]
            for label, key, values, reason in cases:
                with self.subTest(anonymous=anonymous, case=label):
                    altered = Message()
                    for name, value in original.items():
                        if name.lower() != key.lower():
                            altered[name] = value
                    for value in values:
                        altered[key] = value
                    with self.assertRaises(QualificationError) as ctx:
                        validate_twin_http_headers(altered, anonymous=anonymous)
                    self.assertEqual(str(ctx.exception), reason)

    def test_qualifier_never_uses_ambient_proxy_for_loopback_token(self):
        # Real Twin/PostgreSQL CI integration; proxy points to an unavailable
        # loopback listener. The bearer must go directly to Twin, not a proxy.
        with patch.dict(os.environ, {
            "HTTP_PROXY": "http://127.0.0.1:1",
            "HTTPS_PROXY": "http://127.0.0.1:1",
            "ALL_PROXY": "http://127.0.0.1:1",
            "NO_PROXY": "",
            "no_proxy": "",
        }):
            result = qualify(BASE, TOKEN)
        self.assertEqual(result["contract_status"], "PASS")
        self.assertEqual(result["overall"], "NO_GO")

    def test_readonly_qualifier_rejects_forged_paths_and_attestations(self):
        response = self.read("ACME-SAN-FABRIC-A")
        self.assertEqual(response.status_code, 200)
        original = response.json()
        cases = (
            ("fake_outage", lambda d: d.update(runtime_impact_state="DEGRADED")),
            ("fake_tenant_acl", lambda d: d.update(tenant_acl_qualified=True)),
            ("fake_runtime", lambda d: d.update(runtime_authenticated=True)),
            ("fake_provenance", lambda d: d.update(provenance="CMDB_VERIFIED")),
            ("wrong_direction", lambda d: d.update(traversal_direction="FORWARD")),
            ("missing_edge", lambda d: d["shortest_path_edges"].pop()),
            ("wrong_edge_id", lambda d: d["shortest_path_edges"][0].update(
                edge_id="INVENTED-SAN-HOST")),
            ("fake_host", lambda d: d["affected"].append({
                "node_id": "ACME-SRV-RHEL01", "depth": 2})),
            ("missing_payments", lambda d: d["affected"].pop()),
            ("duplicate_node", lambda d: d["affected"].append(
                copy.deepcopy(d["affected"][0]))),
            ("wrong_path_semantics", lambda d: d.update(
                path_semantics="CONFIRMED_PAYMENTS_OUTAGE")),
        )
        for name, mutate in cases:
            with self.subTest(case=name):
                forged = copy.deepcopy(original)
                mutate(forged)
                with self.assertRaises(QualificationError):
                    validate_impact(forged)

    def test_qualifier_rejects_non_loopback_without_network(self):
        for url in ("http://10.79.94.202:811", "https://127.0.0.1:811",
                    "http://localhost:811", "http://127.0.0.1:811/impact",
                    "http://user:pass@127.0.0.1:811",
                    "http://127.0.0.1:811/?token=secret",
                    "http://127.0.0.1:99999", " http://127.0.0.1:811",
                    "http://127.0.0.1:811\n", "http://127.0.0.1:0811",
                    "http://127.0.0.1:811\t"):
            with self.subTest(url=url), self.assertRaises(QualificationError):
                loopback_base(url)
        with self.assertRaises(QualificationError):
            qualify(BASE, "")
        process = subprocess.run(
            [sys.executable, "scripts/qualify_acme_twin_readonly.py",
             "--base-url", "http://10.79.94.202:811"],
            env={**os.environ, "AIOPS_TWIN_READ_TOKEN": TOKEN},
            text=True, capture_output=True, timeout=10, check=False,
        )
        self.assertEqual(process.returncode, 2)
        self.assertEqual(json.loads(process.stdout)["overall"], "NO_GO")
        self.assertNotIn(TOKEN, process.stdout)


    def test_portal_fixture_and_twin_seed_are_not_an_authenticated_join(self):
        # Two independently synthetic models, NOT one canonical runtime CMDB.
        # Portal has SAN -> ESX host; Twin seed has VM -> RHEL host but no
        # SAN -> host edge. A matching business name is not an identity join.
        from app.portal.acme_fixture_contract import load_fixture, validate_fixture

        fixture = load_fixture("app/portal/acme-fixtures.json")
        portal = validate_fixture(fixture)
        self.assertEqual(fixture["provenance"], "SIMULATED_TARGET")
        self.assertEqual(portal["source_incident_id"], "ACME-DEMO-SAN-001")
        self.assertEqual(portal["target_incident_id"], "ACME-DEMO-PAY-002")
        self.assertEqual(portal["impact_path"],
                         ["SAN-FABRIC-A", "HOST-ESX-01", "VM-PAY-01", "APP-PAY-01"])
        portal_ids = {item["id"] for item in fixture["ci"]}
        with psycopg.connect(DATABASE_URL) as c:
            twin_ids = {
                row[0] for row in c.execute(
                    "select node_id from aiops.twin_nodes"
                ).fetchall()
            }
            twin_edges = {
                (row[0], row[1]) for row in c.execute(
                    "select source_id,target_id from aiops.twin_edges"
                ).fetchall()
            }
        self.assertTrue(portal_ids.isdisjoint(twin_ids))
        self.assertIn("SAN-FABRIC-A", portal_ids)
        self.assertIn("APP-PAY-01", portal_ids)
        self.assertIn("ACME-SAN-FABRIC-A", twin_ids)
        self.assertIn("ACME-BIZ-PAYMENTS", twin_ids)
        self.assertIn(("ACME-STO-PURE01", "ACME-SAN-FABRIC-A"), twin_edges)
        self.assertIn(("ACME-VM-PAY01", "ACME-SRV-RHEL01"), twin_edges)
        self.assertNotIn(("ACME-SRV-RHEL01", "ACME-SAN-FABRIC-A"), twin_edges)
        self.assertNotIn(("ACME-SRV-RHEL01", "ACME-STO-PURE01"), twin_edges)
        response = self.read("ACME-SAN-FABRIC-A")
        self.assertEqual(response.status_code, 200)
        impact = response.json()
        self.assertEqual(impact["runtime_impact_state"], "UNKNOWN")
        self.assertIs(impact["tenant_acl_qualified"], False)
        self.assertNotIn("ACME-SRV-RHEL01",
                         {item["node_id"] for item in impact["affected"]})
        # No shared CI ID, no verified alias table, no Policy/Run binding:
        # neither the Portal host path nor a runtime Payments outage may
        # be inferred from this Twin HTTP result.


if __name__ == "__main__":
    unittest.main()
