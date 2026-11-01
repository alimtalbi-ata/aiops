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


    def test_exact_sourced_reverse_path_edge_types(self):
        _, _, edges, _ = seed_contract()
        expected = ("PATH", "USES", "RUNS_ON", "DEPENDS_ON", "USES")
        self.assertEqual(tuple(edges[eid][2] for eid, _, _ in PATH), expected)
        for eid, affected, consumer in PATH:
            with self.subTest(edge_id=eid):
                self.assertEqual(edges[eid][:2], (consumer, affected))
        # Edge confidence and a synthetic graph are not an observed outage.
        self.assertEqual(edges["ACME-E08"][3], 1)
        self.assertEqual(edges["ACME-E09"][3], 1)

    def test_checkpoint_order_does_not_prove_recovery(self):
        _, _, _, steps = seed_contract()
        self.assertEqual([action for _, _, action, _, _ in steps], [
            "INCIDENT_OPEN", "SET_STATE", "OBSERVE", "CHANGE_LOOKUP",
            "POLICY_CHECK", "VERIFY", "RECONCILE",
        ])
        self.assertEqual(steps[4][4], {"requested_action": "HUMAN_APPROVAL"})
        self.assertEqual(steps[5][4], {"latency_ms": 92, "status": "OK"})
        self.assertEqual(steps[6][4]["state"], "DEGRADED")
        self.assertLess(steps[5][1], steps[6][1])
        self.assertFalse(any(action in ("LIVE", "EXECUTE", "GLPI_WRITE")
                             for _, _, action, _, _ in steps))

    def test_fixture_has_no_runtime_identity_or_priority_calculation(self):
        _, sql, _, steps = seed_contract()
        for field in ("tenant_id", "incident_id", "run_id", "evidence_id",
                      "ticket_id", "observed_at", "known_at", "freshness",
                      "provenance", "impact", "urgency", "policy_version"):
            with self.subTest(field=field):
                self.assertNotIn(field, sql)
        self.assertTrue(all(not any(k in payload for k in
                                    ("tenant_id", "incident_id", "run_id",
                                     "evidence_ids", "ticket_id", "observed_at",
                                     "known_at", "impact", "urgency"))
                            for _, _, _, _, payload in steps))


    def test_every_twin_edge_and_scenario_target_resolves_to_unique_seed_ci(self):
        _, sql, edges, steps = seed_contract()
        nodes = re.findall(
            r"^\('(ACME-[^']+)','(?:BUSINESS|SERVICE|APPLICATION|VM|SERVER|STORAGE|SAN|NETWORK|NAS)'",
            sql, flags=re.MULTILINE,
        )
        self.assertEqual(len(nodes), 18)
        self.assertEqual(len(nodes), len(set(nodes)))
        for edge_id, (consumer, dependency, _, _) in edges.items():
            with self.subTest(edge_id=edge_id):
                self.assertIn(consumer, nodes)
                self.assertIn(dependency, nodes)
        for step_no, _, _, target, _ in steps:
            with self.subTest(step_no=step_no):
                self.assertIn(target, nodes)

    def test_seed_edge_identity_and_relationships_are_not_ambiguous(self):
        _, sql, edges, _ = seed_contract()
        rows = EDGE_ROW.findall(sql)
        self.assertEqual(len(rows), 17)
        self.assertEqual(len(rows), len(edges))
        self.assertEqual(len(rows), len({row[0] for row in rows}))
        self.assertEqual(len(rows), len({(row[1], row[2], row[3]) for row in rows}))

    def test_portal_illustration_cannot_be_joined_to_core_seed_ids(self):
        # This older Portal illustration is NOT the canonical Core/Twin seed.
        # It is never a source for Core incident/run/evidence/ticket identity.
        portal_path = SEED_PATH.parents[2] / "app/portal/acme-fixtures.json"
        portal = json.loads(portal_path.read_text(encoding="utf-8"))
        _, sql, edges, _ = seed_contract()
        seed_ci_ids = {node for _, (consumer, dependency, _, _) in edges.items()
                       for node in (consumer, dependency)}
        portal_ci_ids = {ci["id"] for ci in portal["ci"]}
        self.assertEqual(portal["schema"], "aiops.acme.demo.v1")
        self.assertEqual(portal["provenance"], "SIMULATED_TARGET")
        self.assertFalse(seed_ci_ids.intersection(portal_ci_ids))
        self.assertTrue(all(inc["status"] == "simulated" and
                            inc["live_remediation"] is False
                            for inc in portal["incidents"]))
        self.assertFalse(any(field in portal for field in
                             ("tenant_id", "run_id", "evidence_ids", "ticket_id")))
        self.assertNotIn("ACME-DEMO-SAN-001", sql)
        self.assertNotIn("ACME-DEMO-PAY-002", sql)



class AcmeSevenSourceAuthorityNegativeContractTests(unittest.TestCase):
    """Seven local domains, no authenticated Core PG16 or GLPI authority."""

    @classmethod
    def setUpClass(cls):
        from tools import generate_acme_incidents as gen
        from tools import acme_synthetic_source_authority_negative as negative
        cls.gen = gen
        cls.negative = negative
        cls.manifest = gen.replay(seed=20261018)
        cls.expected = negative.build_negative_receipt(cls.manifest)
        cls.fixture = json.loads(negative.FIXTURE.read_text(encoding="utf-8"),
                                 object_pairs_hook=gen._unique_object)

    def test_redacted_machine_receipt_pinned_and_reproducible(self):
        self.assertEqual(self.fixture, self.expected)
        self.assertEqual(self.negative.verify_negative_receipt(
            self.manifest, self.fixture)["result"], "UNAVAILABLE")
        self.assertEqual(self.fixture["source_replay_sha256"],
                         "bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8")
        self.assertEqual(self.fixture["seed"], 20261018)
        self.assertEqual(self.fixture["graph_version"], self.gen.SEED_GIT_BLOB)
        self.assertEqual(hashlib.sha256(self.negative.FIXTURE.read_bytes()).hexdigest(),
                         "3464ced6e31f4cbc28145090d8a89cb8448c54e08a5f948aadada2ff8df202b1")

    def test_each_event_has_three_distinct_local_hashes_and_no_core_hash(self):
        rows = self.fixture["events"]
        self.assertEqual(len(rows), 7)
        self.assertEqual([r["sequence"] for r in rows], list(range(1, 8)))
        self.assertEqual([r["source_event_id"] for r in rows],
                         [e["source_event_id"] for e in self.manifest["events"]])
        for event, row in zip(self.manifest["events"], rows):
            with self.subTest(event=row["source_event_id"]):
                digests = [row[k] for k in self.negative.FIELDS]
                self.assertEqual(len(set(digests)), 3)
                self.assertTrue(all(re.fullmatch(r"[0-9a-f]{64}", h) for h in digests))
                self.assertEqual(digests[0],
                                 hashlib.sha256(self.gen._canonical(event)).hexdigest())
                self.assertEqual(digests[1], hashlib.sha256(
                    self.gen._canonical(event["payload"])).hexdigest())
                self.assertIsNone(row["core_pg16_payload_sha256"])
                self.assertIsNone(row["core_pg16_full_event_sha256"])
                self.assertEqual(row["mapping_status"], "UNAVAILABLE")

    def test_missing_reordered_duplicate_foreign_events_rejected(self):
        import copy
        mutations = (
            lambda c: c["events"].pop(),
            lambda c: c["events"].reverse(),
            lambda c: c["events"].__setitem__(1, copy.deepcopy(c["events"][0])),
            lambda c: c["events"][0].update(source_event_id="FOREIGN-EVENT"),
        )
        for mutate in mutations:
            candidate = copy.deepcopy(self.fixture)
            mutate(candidate)
            with self.assertRaises(ValueError):
                self.negative.verify_negative_receipt(self.manifest, candidate)

    def test_swapped_and_forged_hash_domains_rejected(self):
        import copy
        for field in self.negative.FIELDS:
            candidate = copy.deepcopy(self.fixture)
            candidate["events"][0][field] = "0" * 64
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.negative.verify_negative_receipt(self.manifest, candidate)
        candidate = copy.deepcopy(self.fixture)
        row = candidate["events"][0]
        row[self.negative.FIELDS[0]], row[self.negative.FIELDS[2]] = (
            row[self.negative.FIELDS[2]], row[self.negative.FIELDS[0]])
        with self.assertRaises(ValueError):
            self.negative.verify_negative_receipt(self.manifest, candidate)

    def test_foreign_actor_tenant_runtime_ids_and_fake_core_receipts_rejected(self):
        import copy
        for field, value in (("tenant_id", "FOREIGN"), ("actor_subject", "FOREIGN"),
                             ("incident_id", "FORGED"), ("run_id", "FORGED"),
                             ("glpi_ticket_id", "FORGED"), ("hitl_approval", "APPROVED"),
                             ("freshness", "FRESH"), ("revocation", "NOT_REVOKED")):
            candidate = copy.deepcopy(self.fixture)
            candidate["runtime_authority"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.negative.verify_negative_receipt(self.manifest, candidate)
        candidate = copy.deepcopy(self.fixture)
        candidate["events"][0]["core_pg16_full_event_sha256"] = "a" * 64
        with self.assertRaises(ValueError):
            self.negative.verify_negative_receipt(self.manifest, candidate)

    def test_fifteen_stages_six_checkpoints_remain_unexecuted(self):
        self.assertEqual(self.fixture["itil_stages"],
                         {"count": 15, "status": "NOT_EXECUTED"})
        self.assertEqual(self.fixture["checkpoints"],
                         {"count": 6, "status": "NOT_EXECUTED"})
        self.assertEqual(self.fixture["runtime_readback"], "NOT_EXECUTED")
        self.assertEqual(self.fixture["runtime_authority"]["core_pg16_readback"],
                         "UNAVAILABLE")
        self.assertFalse(self.fixture["publishable_to_core_or_glpi"])
        self.assertFalse(self.fixture["live_effects_authorized"])

    def test_cli_emit_check_byte_identical_and_unavailable(self):
        import subprocess
        import sys
        cmd = [sys.executable, "-m", "tools.acme_synthetic_source_authority_negative"]
        emit = subprocess.run(cmd + ["--emit"], cwd=self.gen.ROOT,
                              capture_output=True, text=True)
        self.assertEqual(emit.returncode, 0, emit.stderr)
        self.assertEqual(emit.stdout.encode("utf-8"),
                         self.negative.FIXTURE.read_bytes())
        check = subprocess.run(cmd + ["--check"], cwd=self.gen.ROOT,
                               capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertEqual(json.loads(check.stdout)["result"], "UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
