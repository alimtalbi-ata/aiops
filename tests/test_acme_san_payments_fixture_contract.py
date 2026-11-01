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


class AcmeCoreSevenReadbackUnknownGateTests(unittest.TestCase):
    """Only offline Core receipt shape checks; never an authenticated readback."""

    @classmethod
    def setUpClass(cls):
        from tools import generate_acme_incidents as gen
        from tools import acme_synthetic_core_readback_unknown_gate as gate
        cls.gen = gen
        cls.gate = gate
        cls.manifest = gen.replay(seed=20261018)
        cls.expected = gate.build_fixture(cls.manifest)
        cls.fixture = json.loads(gate.FIXTURE.read_text(encoding="utf-8"),
                                 object_pairs_hook=gen._unique_object)
        cls.now = 1700000000
        cls.tenant = "TEST_ONLY_TENANT_A"
        cls.actor_hash = hashlib.sha256(b"TEST_ONLY_ACTOR_A").hexdigest()

    def test_redacted_fixture_pins_seven_distinct_local_hash_domains(self):
        self.assertEqual(self.gate.verify_fixture(self.manifest, self.fixture),
                         self.expected)
        self.assertEqual(self.fixture["event_count"], 7)
        self.assertIsNone(self.fixture["core_readback"])
        self.assertEqual(self.fixture["core_pg16_authority"], "UNKNOWN")
        for event, row in zip(self.manifest["events"], self.fixture["events"]):
            with self.subTest(source_event_id=row["source_event_id"]):
                self.assertEqual(row["source_event_id"], event["source_event_id"])
                self.assertEqual(row["acme_full_event_sha256"],
                                 hashlib.sha256(self.gen._canonical(event)).hexdigest())
                self.assertEqual(len({row["acme_full_event_sha256"],
                                      row["acme_local_payload_sha256"],
                                      row["proposed_core_payload_sha256"]}), 3)
                self.assertIsNone(row["core_pg16_payload_sha256"])
                self.assertIsNone(row["core_pg16_full_event_sha256"])
                self.assertEqual(row["mapping_status"], "UNKNOWN")

    def _test_only_shape(self):
        # In-memory adversarial input, NOT a Core receipt or PG16 assertion.
        return {
            "schema": self.gate.CORE_SCHEMA,
            "decision": "UNKNOWN", "link_status": "UNKNOWN",
            "source_preflight": "PASS_SYNTHETIC_ONLY",
            "transport": "TLS_AUTHENTICATED_NONPORTABLE",
            "portable_signature": "NONE",
            "issuer": "TEST_ONLY_ISSUER",
            "source_system": "TEST_ONLY_SOURCE",
            "tenant_id": self.tenant,
            "incident_id": "TEST_ONLY_INCIDENT",
            "run_id": "TEST_ONLY_RUN",
            "glpi_instance_id": "TEST_ONLY_GLPI",
            "ticket_id": "TEST_ONLY_TICKET",
            "glpi_entity_id": "TEST_ONLY_ENTITY",
            "permission": "run:read",
            "actor_issuer": "TEST_ONLY_IDP",
            "actor_subject_sha256": self.actor_hash,
            "source_event_id": self.fixture["events"][0]["source_event_id"],
            "source_payload_hash": "c" * 64,
            "observed_at": self.now - 60,
            "known_at": self.now - 30,
            "expires_at": self.now + 120,
            "event_count": 7,
            "hash_domains": {
                "payload": self.gate.CORE_PAYLOAD_DOMAIN,
                "full_event": self.gate.CORE_FULL_DOMAIN,
                "acme_full_event_equivalence": "NOT_VERIFIED",
            },
            "events": [{
                "sequence": i,
                "source_event_id": row["source_event_id"],
                "evidence_id": "TEST_ONLY_EVIDENCE_" + str(i),
                "payload_sha256": hashlib.sha256(
                    ("TEST_ONLY_CORE_PAYLOAD_" + str(i)).encode()).hexdigest(),
                "full_event_sha256": hashlib.sha256(
                    ("TEST_ONLY_CORE_FULL_" + str(i)).encode()).hexdigest(),
            } for i, row in enumerate(self.fixture["events"], 1)],
            "source_proof_sha256": "a" * 64,
            "receipt_sha256": "b" * 64,
        }

    def _assess(self, supplied=None, *, with_context=True):
        return self.gate.assess_readback(
            self.manifest, supplied,
            expected_tenant=self.tenant if with_context else None,
            expected_actor_sha256=self.actor_hash if with_context else None,
            now=self.now)

    def test_missing_readback_is_unknown_and_unavailable(self):
        result = self._assess()
        self.assertEqual(result["result"], "UNKNOWN")
        self.assertEqual(result["reason"], "NO_INDEPENDENT_CORE_READBACK")
        self.assertEqual(result["core_readback"], "UNAVAILABLE")
        self.assertEqual(result["hash_domain_equivalence"], "UNKNOWN")

    def test_foreign_schema_and_forged_positive_decisions_rejected(self):
        import copy
        for field, value, reason in (
            ("schema", "TEST_ONLY_FOREIGN_SCHEMA", "FOREIGN_CORE_SCHEMA"),
            ("decision", "ALLOW", "UNTRUSTED_AUTHORITY_ASSERTION"),
            ("link_status", "VERIFIED", "UNTRUSTED_AUTHORITY_ASSERTION"),
            ("portable_signature", "SIGNED", "UNTRUSTED_AUTHORITY_ASSERTION"),
        ):
            candidate = copy.deepcopy(self._test_only_shape())
            candidate[field] = value
            with self.subTest(field=field):
                self.assertEqual(self._assess(candidate)["reason"], reason)
                self.assertEqual(self._assess(candidate)["result"], "UNKNOWN")

    def test_missing_reordered_duplicate_and_foreign_events_unknown(self):
        import copy
        for mutate in (
            lambda c: c["events"].pop(),
            lambda c: c["events"].reverse(),
            lambda c: c["events"].__setitem__(1, copy.deepcopy(c["events"][0])),
            lambda c: c["events"][0].update(source_event_id="TEST_ONLY_FOREIGN_EVENT"),
        ):
            candidate = self._test_only_shape()
            mutate(candidate)
            result = self._assess(candidate)
            self.assertEqual(result["result"], "UNKNOWN")
            self.assertIn(result["reason"], (
                "MISSING_OR_EXTRA_EVENTS",
                "FOREIGN_DUPLICATE_OR_REORDERED_EVENTS"))

    def test_foreign_tenant_actor_and_missing_run_glpi_evidence_unknown(self):
        import copy
        for field, value, reason in (
            ("tenant_id", "TEST_ONLY_FOREIGN_TENANT", "FOREIGN_TENANT"),
            ("actor_subject_sha256", "f" * 64, "FOREIGN_ACTOR"),
            ("run_id", "", "MISSING_RUNTIME_SCOPE"),
            ("ticket_id", "", "MISSING_RUNTIME_SCOPE"),
            ("incident_id", "", "MISSING_RUNTIME_SCOPE"),
        ):
            candidate = copy.deepcopy(self._test_only_shape())
            candidate[field] = value
            with self.subTest(field=field):
                self.assertEqual(self._assess(candidate)["reason"], reason)
        candidate = self._test_only_shape()
        candidate["events"][2]["evidence_id"] = ""
        self.assertEqual(self._assess(candidate)["reason"],
                         "MISSING_EVIDENCE_OR_INVALID_CORE_HASH_DOMAINS")

    def test_hash_domain_swaps_and_missing_core_digests_unknown(self):
        import copy
        candidate = self._test_only_shape()
        row = candidate["events"][0]
        row["payload_sha256"], row["full_event_sha256"] = (
            row["full_event_sha256"], row["payload_sha256"])
        # Both are syntactically valid but cannot establish cross-domain equality.
        self.assertEqual(self._assess(candidate)["result"], "UNKNOWN")
        candidate = copy.deepcopy(self._test_only_shape())
        candidate["events"][0]["full_event_sha256"] = None
        self.assertEqual(self._assess(candidate)["reason"],
                         "MISSING_EVIDENCE_OR_INVALID_CORE_HASH_DOMAINS")
        candidate = copy.deepcopy(self._test_only_shape())
        candidate["hash_domains"]["acme_full_event_equivalence"] = "VERIFIED"
        self.assertEqual(self._assess(candidate)["reason"], "FOREIGN_HASH_DOMAIN")

    def test_stale_future_expired_and_revocation_claims_unknown(self):
        for field, value in (
            ("observed_at", self.now - 900),
            ("known_at", self.now + 20),
            ("expires_at", self.now - 1),
        ):
            candidate = self._test_only_shape()
            candidate[field] = value
            with self.subTest(field=field):
                self.assertEqual(self._assess(candidate)["reason"],
                                 "STALE_FUTURE_OR_EXPIRED")
        candidate = self._test_only_shape()
        candidate["revoked"] = False  # not part of Core receipt; no revocation proof
        self.assertEqual(self._assess(candidate)["reason"],
                         "MISSING_OR_UNEXPECTED_CORE_FIELDS")

    def test_even_complete_test_only_shape_never_promotes_core_authority(self):
        result = self._assess(self._test_only_shape())
        self.assertEqual(result["reason"], "NO_INDEPENDENT_PG16_AUTHORITY")
        self.assertEqual(result["result"], "UNKNOWN")
        self.assertEqual(result["core_pg16_authority"], "UNKNOWN")
        for key in ("tenant_id", "actor_subject", "incident_id", "run_id",
                    "glpi_ticket_id", "hitl_approval"):
            self.assertIsNone(result[key])
        self.assertEqual(result["evidence_ids"], [])
        self.assertEqual(result["itil_stages"],
                         {"count": 15, "status": "NOT_EXECUTED"})
        self.assertEqual(result["checkpoints"],
                         {"count": 6, "status": "NOT_EXECUTED"})
        self.assertFalse(result["publishable_to_core_or_glpi"])
        self.assertFalse(result["live_effects_authorized"])

    def test_supplied_shape_without_independent_actor_tenant_context_unknown(self):
        result = self._assess(self._test_only_shape(), with_context=False)
        self.assertEqual(result["reason"], "NO_INDEPENDENT_ACTOR_TENANT_CONTEXT")
        self.assertEqual(result["result"], "UNKNOWN")
        self.assertEqual(result["freshness"], "UNKNOWN")
        self.assertEqual(result["revocation"], "UNKNOWN")

    def test_cli_emit_check_and_readback_redact_test_only_identifiers(self):
        import subprocess
        import sys
        import tempfile
        cmd = [sys.executable, "-m",
               "tools.acme_synthetic_core_readback_unknown_gate"]
        emit = subprocess.run(cmd + ["--emit"], cwd=self.gen.ROOT,
                              capture_output=True, text=True)
        self.assertEqual(emit.returncode, 0, emit.stderr)
        self.assertEqual(json.loads(emit.stdout), self.fixture)
        check = subprocess.run(cmd + ["--check"], cwd=self.gen.ROOT,
                               capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertEqual(json.loads(check.stdout)["result"], "UNKNOWN")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "TEST_ONLY_readback.json"
            path.write_text(json.dumps(self._test_only_shape()), encoding="utf-8")
            proc = subprocess.run(cmd + ["--readback", str(path)],
                                  cwd=self.gen.ROOT, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["result"], "UNKNOWN")
            self.assertNotIn("TEST_ONLY_TENANT_A", proc.stdout)
            self.assertNotIn("TEST_ONLY_INCIDENT", proc.stdout)
            self.assertNotIn("TEST_ONLY_EVIDENCE", proc.stdout)



class AcmeItilStageAuthorityConsumerTests(unittest.TestCase):
    """15 stages and six checkpoints require independent authority, not JSON."""

    @classmethod
    def setUpClass(cls):
        from tools import generate_acme_incidents as gen
        from tools import acme_synthetic_itil_stage_authority_consumer as consumer
        cls.gen = gen
        cls.consumer = consumer
        cls.manifest = gen.replay(seed=20261018)
        cls.fixture = json.loads(consumer.FIXTURE.read_text(encoding="utf-8"),
                                 object_pairs_hook=gen._unique_object)

    def test_machine_receipt_is_pinned_to_offline_itil_and_seven_hash_triples(self):
        receipt = self.consumer.verify_receipt(self.manifest, self.fixture)
        self.assertEqual(receipt["source_event_count"], 7)
        self.assertEqual(receipt["stage_count"], 15)
        self.assertEqual(receipt["checkpoint_count"], 6)
        self.assertEqual(len({s["stage"] for s in receipt["stages"]}), 15)
        self.assertEqual(len({c["stage"] for c in receipt["checkpoints"]}), 6)
        self.assertEqual(len({r["source_event_id"] for r in receipt["source_events"]}), 7)
        for event, row in zip(self.manifest["events"], receipt["source_events"]):
            with self.subTest(source_event_id=row["source_event_id"]):
                self.assertEqual(row["source_event_id"], event["source_event_id"])
                self.assertEqual(row["acme_full_event_sha256"],
                                 hashlib.sha256(self.gen._canonical(event)).hexdigest())
                self.assertEqual(len({row["acme_full_event_sha256"],
                                      row["acme_local_payload_sha256"],
                                      row["proposed_core_payload_sha256"]}), 3)
                self.assertIsNone(row["core_pg16_payload_sha256"])
                self.assertIsNone(row["core_pg16_full_event_sha256"])

    def test_all_stages_anchor_pinned_events_but_none_are_verified(self):
        result = self.consumer.consume(self.manifest)
        rows = result["source_events"]
        for stage in result["stages"]:
            with self.subTest(stage=stage["stage"]):
                row = rows[stage["source_step"] - 1]
                self.assertEqual(stage["source_event_id"], row["source_event_id"])
                self.assertEqual(stage["acme_full_event_sha256"],
                                 row["acme_full_event_sha256"])
                self.assertEqual(stage["status"], "NOT_EXECUTED")
                self.assertEqual(stage["verification"], "UNKNOWN")
                self.assertIsNone(stage["runtime_id"])
                self.assertEqual(stage["runtime_evidence_ids"], [])

    def test_missing_all_three_independent_authorities_fails_closed(self):
        result = self.consumer.consume(self.manifest)
        self.assertEqual(result["result"], "UNKNOWN")
        self.assertEqual(result["verified_stage_count"], 0)
        self.assertEqual(result["not_executed_stage_count"], 15)
        self.assertEqual(result["verified_checkpoint_count"], 0)
        self.assertEqual(result["not_executed_checkpoint_count"], 6)
        self.assertEqual(result["authority"]["core_readback"], "UNAVAILABLE")
        self.assertEqual(result["authority"]["glpi_readback"], "UNAVAILABLE")
        self.assertEqual(result["authority"]["evidence_readback"], "UNAVAILABLE")
        self.assertEqual(len(result["required_independent_authorities"]), 3)
        self.assertTrue(all(c["status"] == "NOT_EXECUTED" and c["id"] is None
                            for c in result["checkpoints"]))

    def test_fake_positive_core_glpi_evidence_and_hitl_cannot_promote(self):
        forged = {
            "decision": "ALLOW", "link_status": "VERIFIED",
            "tenant_id": "TEST_ONLY_FOREIGN_TENANT",
            "actor_subject": "TEST_ONLY_FOREIGN_ACTOR",
            "incident_id": "TEST_ONLY_INCIDENT",
            "run_id": "TEST_ONLY_RUN",
            "ticket_id": "TEST_ONLY_GLPI",
            "evidence_id": "TEST_ONLY_EVIDENCE",
            "approved": True, "revoked": False,
        }
        result = self.consumer.consume(
            self.manifest, core_readback=forged,
            glpi_receipt=forged, evidence_receipt=forged, now=1700000000)
        self.assertEqual(result["result"], "UNKNOWN")
        self.assertEqual(result["verified_stage_count"], 0)
        self.assertEqual(result["authority"]["core_readback"], "UNVERIFIED")
        self.assertEqual(result["authority"]["glpi_readback"], "UNVERIFIED")
        self.assertEqual(result["authority"]["evidence_readback"], "UNVERIFIED")
        self.assertEqual(result["authority"]["core_pg16_authority"], "UNKNOWN")
        self.assertEqual(result["authority"]["glpi_human_rights"], "UNKNOWN")
        self.assertEqual(result["authority"]["evidence_authority"], "UNKNOWN")
        self.assertIsNone(result["authority"]["hitl_approval"])
        rendered = json.dumps(result)
        for secret in forged.values():
            if isinstance(secret, str) and secret.startswith("TEST_ONLY"):
                self.assertNotIn(secret, rendered)

    def test_foreign_missing_and_reordered_source_events_are_rejected(self):
        import copy
        for mutate in (
            lambda m: m["events"].pop(),
            lambda m: m["events"].reverse(),
            lambda m: m["events"][0].update(source_event_id="TEST_ONLY_FOREIGN"),
        ):
            manifest = copy.deepcopy(self.manifest)
            mutate(manifest)
            with self.assertRaises(ValueError):
                self.consumer.consume(manifest)

    def test_missing_reordered_and_forged_verified_stages_are_rejected(self):
        import copy
        for mutate in (
            lambda c: c["stages"].pop(),
            lambda c: c["stages"].reverse(),
            lambda c: c["stages"][0].update(status="VERIFIED"),
            lambda c: c["stages"][1].update(runtime_id="TEST_ONLY_INCIDENT"),
            lambda c: c["stages"][2].update(verification="VERIFIED"),
            lambda c: c["checkpoints"][0].update(status="VERIFIED", id="TEST_ONLY_GLPI"),
        ):
            candidate = copy.deepcopy(self.fixture)
            mutate(candidate)
            with self.assertRaises(ValueError):
                self.consumer.verify_receipt(self.manifest, candidate)

    def test_mismatched_local_hash_or_forged_core_hash_rejected(self):
        import copy
        for field, value in (
            ("acme_full_event_sha256", "a" * 64),
            ("core_pg16_full_event_sha256", "b" * 64),
            ("core_pg16_payload_sha256", "c" * 64),
        ):
            candidate = copy.deepcopy(self.fixture)
            candidate["source_events"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.consumer.verify_receipt(self.manifest, candidate)

    def test_fake_core_shape_and_foreign_glpi_evidence_never_verify(self):
        supplied = {"schema": "aiops.core-canonical-seven-source-receipt.v1",
                    "events": [], "decision": "VERIFIED",
                    "tenant_id": "TEST_ONLY_FOREIGN"}
        result = self.consumer.consume(
            self.manifest, core_readback=supplied,
            glpi_receipt={"rights": "ALLOW", "tenant": "TEST_ONLY_FOREIGN"},
            evidence_receipt={"hash": "f" * 64, "verified": True},
            now=1700000000)
        self.assertEqual(result["result"], "UNKNOWN")
        self.assertNotEqual(result["authority"]["core_shape_reason"],
                            "NO_INDEPENDENT_PG16_AUTHORITY")
        self.assertEqual(result["not_executed_stage_count"], 15)
        self.assertEqual(result["not_executed_checkpoint_count"], 6)

    def test_invalid_nonobject_and_forged_authority_counts_rejected(self):
        import copy
        with self.assertRaises(ValueError):
            self.consumer.consume(self.manifest, glpi_receipt=["ALLOW"])
        candidate = copy.deepcopy(self.fixture)
        candidate["verified_stage_count"] = 1
        with self.assertRaises(ValueError):
            self.consumer.consume(self.manifest, candidate=candidate)
        candidate = copy.deepcopy(self.fixture)
        candidate["authority"]["actor_subject"] = "TEST_ONLY_ACTOR"
        with self.assertRaises(ValueError):
            self.consumer.consume(self.manifest, candidate=candidate)

    def test_cli_emit_check_and_untrusted_inputs_are_redacted(self):
        import subprocess
        import sys
        import tempfile
        cmd = [sys.executable, "-m",
               "tools.acme_synthetic_itil_stage_authority_consumer"]
        emit = subprocess.run(cmd + ["--emit"], cwd=self.gen.ROOT,
                              capture_output=True, text=True)
        self.assertEqual(emit.returncode, 0, emit.stderr)
        self.assertEqual(emit.stdout.encode("utf-8"),
                         self.consumer.FIXTURE.read_bytes())
        check = subprocess.run(cmd + ["--check"], cwd=self.gen.ROOT,
                               capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertEqual(json.loads(check.stdout)["verified_stage_count"], 0)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "untrusted.json"
            path.write_text(json.dumps({"secret": "TEST_ONLY_BEARER",
                                        "decision": "ALLOW"}), encoding="utf-8")
            proc = subprocess.run(cmd + ["--core-readback", str(path),
                                         "--glpi-receipt", str(path),
                                         "--evidence-receipt", str(path)],
                                  cwd=self.gen.ROOT, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("TEST_ONLY_BEARER", proc.stdout)
            self.assertEqual(json.loads(proc.stdout)["verified_stage_count"], 0)


if __name__ == "__main__":
    unittest.main()
