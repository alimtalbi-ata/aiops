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



# Core #291 informational source receipt: offline, adversarial shape ONLY.
# These TEST_ONLY placeholders are not Core/GLPI/PG16 receipts or runtime IDs.
import copy as _copy
from tools import generate_acme_incidents as _acme_gen
from tools import acme_synthetic_three_domain_receipt as _three
from tools import acme_synthetic_core_source_receipt_gate as _receipt_gate


class AcmeCoreSourceReceiptShapeGapTests(unittest.TestCase):
    NOW = 2_000_000_000
    TEST_TENANT = "TEST_ONLY_TENANT_A"
    TEST_ACTOR = "TEST_ONLY_ACTOR_A"

    @classmethod
    def setUpClass(cls):
        cls.manifest = _acme_gen.replay(seed=20261018)
        cls.local = _three.build_receipt(cls.manifest)

    def candidate(self):
        rows = self.local["source_event_rows"]
        events = [{
            "sequence": i,
            "source_event_id": r["source_event_id"],
            "evidence_id": "TEST_ONLY_EVIDENCE_" + str(i),
            "payload_sha256": format(i + 10, "064x"),
            "full_event_sha256": format(i + 20, "064x"),
        } for i, r in enumerate(rows, 1)]
        candidate = {
            "schema": _receipt_gate.CORE_RECEIPT_SCHEMA,
            "decision": "UNKNOWN", "link_status": "UNKNOWN",
            "source_preflight": "PASS_SYNTHETIC_ONLY",
            "transport": "TLS_AUTHENTICATED_NONPORTABLE",
            "portable_signature": "NONE",
            "issuer": "TEST_ONLY_ISSUER",
            "source_system": "CORE_CANONICAL_READBACK",
            "tenant_id": self.TEST_TENANT,
            "incident_id": "TEST_ONLY_INCIDENT",
            "run_id": "TEST_ONLY_RUN",
            "glpi_instance_id": "TEST_ONLY_GLPI_INSTANCE",
            "ticket_id": "TEST_ONLY_TICKET",
            "glpi_entity_id": "TEST_ONLY_ENTITY",
            "permission": "run:read",
            "actor_issuer": "TEST_ONLY_ACTOR_ISSUER",
            "actor_subject_sha256": hashlib.sha256(self.TEST_ACTOR.encode()).hexdigest(),
            "source_event_id": events[0]["source_event_id"],
            "source_payload_hash": events[0]["payload_sha256"],
            "observed_at": self.NOW - 60,
            "known_at": self.NOW - 30,
            "expires_at": self.NOW + 120,
            "event_count": 7,
            "hash_domains": {
                "payload": _receipt_gate.CORE_PAYLOAD_DOMAIN,
                "full_event": _receipt_gate.CORE_FULL_DOMAIN,
                "acme_full_event_equivalence": "NOT_VERIFIED",
            },
            "events": events,
            "source_proof_sha256": "c" * 64,
        }
        self.rehash(candidate)
        return candidate

    @staticmethod
    def rehash(candidate):
        candidate["receipt_sha256"] = _receipt_gate.core_receipt_digest({
            k: v for k, v in candidate.items() if k != "receipt_sha256"})

    def inspect(self, candidate):
        return _receipt_gate.inspect_untrusted_receipt(
            self.manifest, candidate=candidate, now=self.NOW,
            expected_test_tenant=self.TEST_TENANT,
            expected_test_actor_sha256=hashlib.sha256(
                self.TEST_ACTOR.encode()).hexdigest())

    def test_absent_core_receipt_stays_unavailable_and_all_stages_not_executed(self):
        result = _receipt_gate.inspect_untrusted_receipt(self.manifest)
        self.assertEqual(result["result"], "UNAVAILABLE")
        self.assertEqual(result["core_receipt_shape"], "NOT_SUPPLIED")
        self.assertEqual(len(result["source_event_ids"]), 7)
        self.assertEqual(len(result["itil_stages"]), 15)
        self.assertEqual(len(result["checkpoints"]), 6)
        self.assertTrue(all(x["status"] == "NOT_EXECUTED"
                            for x in result["itil_stages"] + result["checkpoints"]))

    def test_test_only_core_style_shape_never_promotes_authority(self):
        result = self.inspect(self.candidate())
        self.assertEqual(result["core_receipt_shape"], "PASS_UNTRUSTED_TEST_INPUT_ONLY")
        self.assertEqual(result["result"], "UNAVAILABLE")
        self.assertEqual(result["cross_domain_equivalence"], "NOT_VERIFIED")
        for field in ("tenant_id", "actor_subject", "incident_id", "run_id",
                      "glpi_ticket_id", "hitl_approval"):
            self.assertIsNone(result[field])
        self.assertEqual(result["evidence_ids"], [])
        self.assertFalse(result["transport_authenticated"])
        self.assertFalse(result["tenant_authorized"])
        self.assertFalse(result["revocation_checked"])

    def test_foreign_tenant_denied_even_with_rehashed_shape(self):
        c = self.candidate()
        c["tenant_id"] = "TEST_ONLY_TENANT_B"
        self.rehash(c)
        with self.assertRaisesRegex(ValueError, "foreign TEST_ONLY tenant"):
            self.inspect(c)

    def test_foreign_actor_denied_even_with_rehashed_shape(self):
        c = self.candidate()
        c["actor_subject_sha256"] = hashlib.sha256(b"TEST_ONLY_ACTOR_B").hexdigest()
        self.rehash(c)
        with self.assertRaisesRegex(ValueError, "foreign TEST_ONLY actor"):
            self.inspect(c)

    def test_missing_or_duplicate_event_denied(self):
        for change in ("missing", "duplicate"):
            with self.subTest(change=change):
                c = self.candidate()
                if change == "missing":
                    c["events"].pop()
                else:
                    c["events"][1]["source_event_id"] = c["events"][0]["source_event_id"]
                self.rehash(c)
                with self.assertRaisesRegex(ValueError, "seven events|foreign, missing"):
                    self.inspect(c)

    def test_reordered_event_denied(self):
        c = self.candidate()
        c["events"][0], c["events"][1] = c["events"][1], c["events"][0]
        self.rehash(c)
        with self.assertRaisesRegex(ValueError, "reordered event"):
            self.inspect(c)

    def test_swapped_core_hash_domains_denied(self):
        c = self.candidate()
        c["events"][0]["payload_sha256"], c["events"][0]["full_event_sha256"] = (
            c["events"][0]["full_event_sha256"], c["events"][0]["payload_sha256"])
        c["source_payload_hash"] = c["events"][0]["payload_sha256"]
        self.rehash(c)
        # Swapping two opaque valid Core-shaped hashes cannot be authenticated
        # by an offline ACME parser: it MUST remain UNAVAILABLE, not VERIFIED.
        self.assertEqual(self.inspect(c)["result"], "UNAVAILABLE")

    def test_acme_hash_masquerading_as_core_hash_denied(self):
        c = self.candidate()
        c["events"][0]["payload_sha256"] = self.local["source_event_rows"][0][
            "acme_full_event_sha256"]
        c["source_payload_hash"] = c["events"][0]["payload_sha256"]
        self.rehash(c)
        with self.assertRaisesRegex(ValueError, "domains conflated"):
            self.inspect(c)

    def test_stale_and_future_receipts_denied(self):
        for key, value in (("observed_at", self.NOW - 301),
                           ("known_at", self.NOW + 1),
                           ("expires_at", self.NOW - 1)):
            with self.subTest(key=key):
                c = self.candidate()
                c[key] = value
                self.rehash(c)
                with self.assertRaisesRegex(ValueError, "stale, future"):
                    self.inspect(c)

    def test_boolean_timestamp_denied(self):
        c = self.candidate()
        c["known_at"] = True
        self.rehash(c)
        with self.assertRaisesRegex(ValueError, "boolean timestamp"):
            self.inspect(c)

    def test_revocation_cannot_be_inferred_from_core_receipt_shape(self):
        c = self.candidate()
        c["revoked"] = False  # forged field: Core informational receipt has no revocation proof
        self.rehash(c)
        with self.assertRaisesRegex(ValueError, "missing or extra"):
            self.inspect(c)

    def test_fake_portable_signature_or_allow_denied(self):
        for field, value in (("portable_signature", "SIGNED"),
                             ("decision", "ALLOW"),
                             ("source_preflight", "PASS_LIVE")):
            with self.subTest(field=field):
                c = self.candidate()
                c[field] = value
                self.rehash(c)
                with self.assertRaisesRegex(ValueError, "forged authority"):
                    self.inspect(c)

    def test_receipt_digest_tampering_denied(self):
        c = self.candidate()
        c["receipt_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            self.inspect(c)

    def test_source_event_outside_seven_denied(self):
        c = self.candidate()
        c["source_event_id"] = "TEST_ONLY_FOREIGN_EVENT"
        self.rehash(c)
        with self.assertRaisesRegex(ValueError, "outside pinned replay"):
            self.inspect(c)

    def test_duplicate_test_only_evidence_denied(self):
        c = self.candidate()
        c["events"][1]["evidence_id"] = c["events"][0]["evidence_id"]
        self.rehash(c)
        with self.assertRaisesRegex(ValueError, "duplicate TEST_ONLY evidence"):
            self.inspect(c)

    def test_unpinned_replay_tamper_denied_before_receipt_comparison(self):
        changed = _copy.deepcopy(self.manifest)
        changed["events"][0]["payload"]["tampered"] = True
        with self.assertRaises(ValueError):
            _receipt_gate.inspect_untrusted_receipt(changed, candidate=self.candidate(),
                                                     now=self.NOW)


if __name__ == "__main__":
    unittest.main()
