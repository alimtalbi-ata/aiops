"""Pinned, offline ACME SAN→Payments fixture contract; no API or runtime effects.

The stored Twin edges point from consumer to dependency. The customer-story
SAN→Payments narrative traverses those edges in reverse and is SYNTHETIC ONLY.
"""
import hashlib
import json
from pathlib import Path
import re
import unittest

SEED_PATH = Path(__file__).resolve().parents[1] / "db/migrations/005_seed_acme.sql"
SEED_GIT_BLOB = "67f0124a2c3b450e5249165e719a5d943fdd7237"
SCENARIO = "SCN-GOLDEN-PAYMENT-P1"
EDGE_ROW = re.compile(r"\('(ACME-E\d{2})','([^']+)','([^']+)','([^']+)',(\d+),([.\d]+)\)")
STEP_ROW = re.compile(r"\('SCN-GOLDEN-PAYMENT-P1',(\d+),(\d+),'([^']+)','([^']+)','([^']+)'\)")
PATH = (
    ("ACME-E08", "ACME-SAN-FABRIC-A", "ACME-STO-PURE01"),
    ("ACME-E06", "ACME-STO-PURE01", "ACME-VM-PAY01"),
    ("ACME-E04", "ACME-VM-PAY01", "ACME-APP-ORACLEPAY"),
    ("ACME-E02", "ACME-APP-ORACLEPAY", "ACME-SVC-PAYMENTS"),
    ("ACME-E01", "ACME-SVC-PAYMENTS", "ACME-BIZ-PAYMENTS"),
)


def seed_contract():
    raw = SEED_PATH.read_bytes()
    sql = raw.decode("utf-8")
    edges = {eid: (src, dst, rel, int(redundancy))
             for eid, src, dst, rel, redundancy, _ in EDGE_ROW.findall(sql)}
    steps = [(int(n), int(t), action, node, json.loads(payload))
             for n, t, action, node, payload in STEP_ROW.findall(sql)]
    return raw, sql, edges, steps


class AcmeSanPaymentsFixtureContractTests(unittest.TestCase):
    def test_exact_fixture_blob_and_scenario_version(self):
        raw, sql, _, _ = seed_contract()
        blob = b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
        self.assertEqual(hashlib.sha1(blob).hexdigest(), SEED_GIT_BLOB)
        self.assertIn("('SCN-GOLDEN-PAYMENT-P1','Golden Payment SAN degradation',20261018,true,", sql)

    def test_single_canonical_reverse_dependency_path(self):
        _, _, edges, _ = seed_contract()
        self.assertEqual(len(edges), 17)
        for eid, affected, dependency_consumer in PATH:
            with self.subTest(edge_id=eid):
                source, target, _, _ = edges[eid]
                self.assertEqual((source, target), (dependency_consumer, affected))
        self.assertTrue(all(src != "ACME-SAN-FABRIC-A" for src, _, _, _ in edges.values()))

    def test_redundant_fabric_b_and_vm_b_are_preserved(self):
        _, _, edges, _ = seed_contract()
        self.assertEqual(edges["ACME-E09"][:2], ("ACME-STO-PURE01", "ACME-SAN-FABRIC-B"))
        self.assertEqual(edges["ACME-E07"][:2], ("ACME-VM-PAY02", "ACME-STO-PURE01"))
        self.assertEqual(edges["ACME-E05"][:2], ("ACME-APP-ORACLEPAY", "ACME-VM-PAY02"))
        self.assertEqual(edges["ACME-E06"][3], 2)

    def test_steps_are_deterministic_and_synthetic(self):
        _, sql, _, steps = seed_contract()
        self.assertEqual([n for n, _, _, _, _ in steps], list(range(1, 8)))
        self.assertEqual([t for _, t, _, _, _ in steps], [0, 15, 30, 45, 60, 90, 110])
        self.assertIn("20261018,true", sql)
        self.assertEqual(steps[1][2:4], ("SET_STATE", "ACME-SAN-FABRIC-A"))

    def test_p1_is_scenario_severity_not_measured_payments_impact(self):
        _, _, _, steps = seed_contract()
        self.assertEqual(steps[0][4]["severity"], "P1")
        self.assertEqual(steps[2][3], "ACME-SAN-FABRIC-A")
        self.assertEqual(steps[2][4]["metric"], "fc_errors")
        self.assertEqual(steps[2][4]["value"], 184)
        self.assertEqual(steps[5][3], "ACME-SVC-PAYMENTS")
        self.assertEqual(steps[5][4], {"latency_ms": 92, "status": "OK"})
        self.assertTrue(all("impact" not in p and "urgency" not in p for *_, p in steps))

    def test_no_runtime_tenant_ticket_or_freshness_attestation_in_seed(self):
        _, sql, _, _ = seed_contract()
        for field in ("tenant_id", "ticket_id", "observed_at", "known_at"):
            with self.subTest(field=field):
                self.assertNotIn(field, sql)


if __name__ == "__main__":
    unittest.main()
