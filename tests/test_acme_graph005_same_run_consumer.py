"""ACME-owned negative/shape regressions for Core #338 same-Run readback.

All test receipts are constructed in memory; they are NOT PG16/HTTPS evidence.
The source-only CI artifact is independently owned by Core. No human ALLOW.
"""
import copy
import hashlib
import json
import unittest

from tools import acme_graph005_same_run_consumer as consumer
from tools import acme_synthetic_pg16_seven_bridge as bridge
from tools import generate_acme_incidents as gen


class AcmeGraph005SameRunConsumerTests(unittest.TestCase):
    NOW = 1700000000

    def setUp(self):
        self.manifest = gen.replay(seed=20261018)
        self.local = bridge.build_receipt(self.manifest)
        self.claims = {"sub": "TEST_ONLY_ACTOR_A",
                       "iss": "TEST_ONLY_IDP_A", "exp": self.NOW + 120}
        self.source_issuer = "TEST_ONLY_CORE_SOURCE_ISSUER"
        self.expected = {
            "tenant_id": "TEST_ONLY_TENANT_A",
            "incident_id": "TEST_ONLY_INCIDENT_A",
            "run_id": "TEST_ONLY_RUN_A",
            "glpi_instance_id": "TEST_ONLY_GLPI_INSTANCE",
            "ticket_id": "TEST_ONLY_TICKET_A",
            "glpi_entity_id": "TEST_ONLY_ENTITY_A",
            "permission": "run:read",
        }
        rows = []
        for n, row in enumerate(self.local["events"], 1):
            rows.append({
                "sequence": consumer.PHYSICAL_SEQUENCES[n - 1],
                "source_event_id": row["source_event_id"],
                "evidence_id": "TEST_ONLY_EVIDENCE_" + str(n),
                "payload_sha256": hashlib.sha256(
                    ("TEST_ONLY_CORE_PAYLOAD_" + str(n)).encode()).hexdigest(),
                "full_event_sha256": hashlib.sha256(
                    ("TEST_ONLY_CORE_FULL_" + str(n)).encode()).hexdigest(),
            })
        self.record = dict(
            source_event_id=rows[0]["source_event_id"],
            source_payload_hash=rows[0]["payload_sha256"],
            **{k: self.expected[k] for k in (
                "tenant_id", "incident_id", "run_id", "glpi_entity_id")})
        self.receipt = {
            "schema": consumer.RECEIPT_SCHEMA,
            "decision": "UNKNOWN", "link_status": "UNKNOWN",
            "source_preflight": "PASS_SYNTHETIC_ONLY",
            "transport": "TLS_AUTHENTICATED_NONPORTABLE",
            "portable_signature": "NONE",
            "issuer": self.source_issuer,
            "source_system": "CORE_CANONICAL_READBACK",
            **self.expected,
            "actor_issuer": self.claims["iss"],
            "actor_subject_sha256": hashlib.sha256(
                self.claims["sub"].encode()).hexdigest(),
            "source_event_id": self.record["source_event_id"],
            "source_payload_hash": self.record["source_payload_hash"],
            "observed_at": self.NOW - 30,
            "known_at": self.NOW - 5,
            "expires_at": self.NOW + 60,
            "event_count": 7,
            "hash_domains": copy.deepcopy(consumer.CORE_DOMAINS),
            "events": rows,
            "source_proof_sha256": hashlib.sha256(
                b"TEST_ONLY_UNAUTHENTICATED_PROOF").hexdigest(),
        }
        self.sign_untrusted()

    def sign_untrusted(self):
        # This is only a reproducible content checksum, never a signature.
        self.receipt["receipt_sha256"] = consumer._digest(
            consumer.RECEIPT_DOMAIN,
            {k: v for k, v in self.receipt.items() if k != "receipt_sha256"})

    def consume(self, *, receipt=None, seen=None, claims=None, expected=None,
                record=None, source_issuer=None, now=None):
        return consumer.consume(
            self.manifest, receipt=self.receipt if receipt is None else receipt,
            claims=self.claims if claims is None else claims,
            expected=self.expected if expected is None else expected,
            record=self.record if record is None else record,
            source_issuer=self.source_issuer if source_issuer is None
            else source_issuer,
            now=self.NOW if now is None else now,
            seen_receipt_hashes=seen)

    def assert_no_authority(self, result):
        self.assertEqual(result["core_pg16_authority"], "UNKNOWN")
        self.assertEqual(result["actor_idp_authority"], "UNKNOWN")
        self.assertEqual(result["glpi_human_allow"], "UNKNOWN")
        self.assertEqual(result["hitl_approval"], "UNKNOWN")
        self.assertEqual(result["runtime_incident_id"], None)
        self.assertEqual(result["runtime_run_id"], None)
        self.assertEqual(result["itil_stages"]["verified"], 0)
        self.assertEqual(result["itil_stages"]["not_executed"], 15)
        self.assertEqual(result["human_checkpoints"]["verified"], 0)
        self.assertEqual(result["human_checkpoints"]["not_executed"], 6)
        self.assertFalse(result["publishable_to_core_or_glpi"])
        self.assertFalse(result["live_effects_authorized"])
        self.assertEqual(result["release_stable"], "NO_GO")
        rendered = json.dumps(result)
        for secret in ("TEST_ONLY_ACTOR_A", "TEST_ONLY_TENANT_A",
                       "TEST_ONLY_INCIDENT_A", "TEST_ONLY_RUN_A",
                       "TEST_ONLY_TICKET_A", "TEST_ONLY_EVIDENCE_1"):
            self.assertNotIn(secret, rendered)

    def test_01_no_source_and_no_replay_guard_fail_closed(self):
        empty = consumer.consume(self.manifest)
        self.assertEqual(empty["source_reason"], "NO_INDEPENDENT_CORE_READBACK")
        self.assertEqual(empty["source_concordance"], "UNKNOWN")
        self.assert_no_authority(empty)
        result = self.consume()
        self.assertEqual(result["source_reason"], "REPLAY_GUARD_UNAVAILABLE")
        self.assertEqual(result["source_concordance"], "UNKNOWN")
        self.assert_no_authority(result)

    def test_02_exact_seven_interleaved_source_and_twin_candidate_impact(self):
        result = self.consume(seen=set())
        self.assertEqual(result["source_concordance"], "CONSISTENT_UNTRUSTED")
        self.assertEqual(result["source_reason"], "NONPORTABLE_SOURCE_SHAPE_ONLY")
        self.assertEqual(result["physical_run_sequences"], [1, 2, 4, 5, 6, 8, 9])
        self.assertEqual(result["source_ordinals"], list(range(1, 8)))
        self.assertEqual([r["source_event_id"] for r in result["events"]],
                         [r["source_event_id"] for r in self.local["events"]])
        self.assertEqual(result["twin_impact"]["candidate_ci_count"], 10)
        self.assertEqual(result["twin_impact"]["source_ci_id"],
                         "ACME-SAN-FABRIC-A")
        self.assertEqual(result["twin_impact"]["selected_service_id"],
                         "ACME-SVC-PAYMENTS")
        self.assertEqual(result["observed_payments_outage"], "UNKNOWN")
        self.assertEqual(result["core_https_runtime_authentication"], "NOT_ATTESTED")
        self.assertEqual(result["durable_replay_fence"], "NOT_ATTESTED")
        self.assertTrue(all(r["domain_equivalence"] ==
                            "DISTINCT_DOMAINS_NOT_EQUIVALENT"
                            for r in result["events"]))
        self.assert_no_authority(result)

    def test_03_in_process_replay_rejected_without_durable_claim(self):
        seen = set()
        first = self.consume(seen=seen)
        self.assertEqual(first["source_concordance"], "CONSISTENT_UNTRUSTED")
        self.assertEqual(len(seen), 1)
        second = self.consume(seen=seen)
        self.assertEqual(second["source_reason"], "REPLAYED_CORE_RECEIPT")
        self.assertEqual(second["source_concordance"], "UNKNOWN")
        self.assertEqual(len(seen), 1)
        self.assert_no_authority(second)

    def test_04_missing_eighth_duplicate_reordered_source_rejected(self):
        mutations = (
            lambda r: r["events"].pop(),
            lambda r: r["events"].append(copy.deepcopy(r["events"][0])),
            lambda r: r["events"].reverse(),
            lambda r: r["events"][1].update(
                source_event_id=r["events"][0]["source_event_id"]),
        )
        for mutate in mutations:
            with self.subTest(mutation=str(mutate)):
                self.setUp()
                mutate(self.receipt)
                self.sign_untrusted()
                result = self.consume(seen=set())
                self.assertEqual(result["source_concordance"], "UNKNOWN")
                self.assert_no_authority(result)

    def test_05_physical_sequence_not_source_ordinal_or_normalized_hash(self):
        for index, seq in ((2, 3), (5, 6), (6, 7), (0, 2)):
            with self.subTest(index=index, sequence=seq):
                self.setUp()
                self.receipt["events"][index]["sequence"] = seq
                self.sign_untrusted()
                result = self.consume(seen=set())
                self.assertEqual(result["source_reason"],
                                 "FOREIGN_REORDERED_DUPLICATE_OR_FORGED_SOURCE")
                self.assert_no_authority(result)

    def test_06_full_payload_hash_domains_and_record_are_distinct(self):
        for mutation in ("swap", "collapse", "bad", "record"):
            with self.subTest(mutation=mutation):
                self.setUp()
                row = self.receipt["events"][0]
                if mutation == "swap":
                    row["payload_sha256"], row["full_event_sha256"] = (
                        row["full_event_sha256"], row["payload_sha256"])
                elif mutation == "collapse":
                    row["full_event_sha256"] = row["payload_sha256"]
                elif mutation == "bad":
                    row["payload_sha256"] = "not-a-hash"
                else:
                    self.record["source_payload_hash"] = "f" * 64
                self.sign_untrusted()
                result = self.consume(seen=set())
                self.assertEqual(result["source_concordance"], "UNKNOWN")
                self.assert_no_authority(result)

    def test_07_foreign_actor_tenant_incident_run_and_issuer_rejected(self):
        mutations = (
            lambda: self.receipt.update(actor_issuer="TEST_ONLY_FOREIGN_IDP"),
            lambda: self.receipt.update(actor_subject_sha256="0" * 64),
            lambda: self.receipt.update(tenant_id="TEST_ONLY_FOREIGN_TENANT"),
            lambda: self.receipt.update(incident_id="TEST_ONLY_FOREIGN_INCIDENT"),
            lambda: self.receipt.update(run_id="TEST_ONLY_FOREIGN_RUN"),
            lambda: self.receipt.update(issuer="TEST_ONLY_FOREIGN_CORE"),
            lambda: self.receipt.update(permission="run:write"),
        )
        for mutate in mutations:
            self.setUp()
            mutate()
            self.sign_untrusted()
            result = self.consume(seen=set())
            self.assertEqual(result["source_reason"],
                             "FOREIGN_ACTOR_TENANT_ISSUER_OR_HASH_DOMAIN")
            self.assert_no_authority(result)
        result = self.consume(seen=set(), source_issuer=self.claims["iss"])
        self.assertEqual(result["source_reason"],
                         "UNPINNED_ACTOR_SOURCE_OR_RUNTIME_SCOPE")

    def test_08_stale_expired_future_or_claim_expired_rejected(self):
        for key, value in (("observed_at", self.NOW - 301),
                           ("known_at", self.NOW + 1),
                           ("expires_at", self.NOW),
                           ("expires_at", self.NOW + 301)):
            self.setUp()
            self.receipt[key] = value
            self.sign_untrusted()
            result = self.consume(seen=set())
            self.assertEqual(result["source_reason"],
                             "STALE_FUTURE_EXPIRED_OR_REVOKED_SCOPE")
            self.assert_no_authority(result)
        claims = dict(self.claims, exp=self.NOW - 1)
        self.assertEqual(self.consume(seen=set(), claims=claims)["source_reason"],
                         "UNPINNED_ACTOR_SOURCE_OR_RUNTIME_SCOPE")

    def test_09_forged_positive_human_or_extra_receipt_fields_rejected(self):
        for key, value in (("decision", "ALLOW"), ("link_status", "VERIFIED"),
                           ("portable_signature", "SIGNED"),
                           ("revoked", False), ("human_glpi_attested", True)):
            self.setUp()
            self.receipt[key] = value
            self.sign_untrusted()
            result = self.consume(seen=set())
            self.assertEqual(result["source_concordance"], "UNKNOWN")
            self.assert_no_authority(result)

    def test_10_corrupt_receipt_hash_rejected_and_not_a_signature(self):
        self.receipt["receipt_sha256"] = "a" * 64
        result = self.consume(seen=set())
        self.assertEqual(result["source_reason"], "FORGED_OR_CORRUPT_RECEIPT_HASH")
        self.assert_no_authority(result)
        self.setUp()
        self.receipt["source_proof_sha256"] = "bad"
        self.sign_untrusted()
        self.assertEqual(self.consume(seen=set())["source_reason"],
                         "FORGED_OR_CORRUPT_RECEIPT_HASH")


    def worker_projection(self):
        """TEST_ONLY projection of Core #338 + Worker #340 harness, not API."""
        source = {r["sequence"]: r for r in self.receipt["events"]}
        rows = []
        for sequence in range(1, 11):
            if sequence in source:
                core = source[sequence]
                row = {
                    "stage": "SOURCE", "event_type": "OBSERVED",
                    "status": "PASS", "decision": None,
                    "event_key": core["source_event_id"],
                    "source_event_id": core["source_event_id"],
                    "payload_sha256": core["payload_sha256"],
                    "full_event_sha256": core["full_event_sha256"],
                }
            else:
                stage, status, decision, key = (
                    consumer.WORKER_HARNESS_PROJECTION[sequence])
                row = {
                    "stage": stage, "event_type": "WORKFLOW_OBSERVATION",
                    "status": status, "decision": decision,
                    "event_key": key, "source_event_id": None,
                    "payload_sha256": hashlib.sha256(
                        ("TEST_ONLY_WORKER_PAYLOAD_" + str(sequence)).encode()
                    ).hexdigest(),
                    "full_event_sha256": hashlib.sha256(
                        ("TEST_ONLY_WORKER_FULL_" + str(sequence)).encode()
                    ).hexdigest(),
                }
            rows.append({
                "sequence": sequence,
                **{k: self.expected[k] for k in (
                    "tenant_id", "incident_id", "run_id")},
                **row,
            })
        return rows

    def joined(self, rows, *, seen=None, receipt=None, claims=None):
        return consumer.consume_joined_worker_projection(
            self.manifest, run_events=rows,
            receipt=self.receipt if receipt is None else receipt,
            claims=self.claims if claims is None else claims,
            expected=self.expected, record=self.record,
            source_issuer=self.source_issuer, now=self.NOW,
            seen_receipt_hashes=seen)

    def assert_join_has_no_human_or_production_authority(self, result):
        self.assert_no_authority(result)
        self.assertEqual(result["worker_production_authority"], "UNKNOWN")
        self.assertEqual(result["core_terminal_014_joined"], "NOT_ATTESTED")
        self.assertEqual(result["core_outbox_replay_joined"], "NOT_ATTESTED")
        self.assertNotIn("TEST_ONLY_WORKER", json.dumps(result))

    def test_11_joined_worker_interleaving_is_shape_only(self):
        result = self.joined(self.worker_projection(), seen=set())
        self.assertEqual(result["worker_projection_concordance"],
                         "CONSISTENT_UNTRUSTED")
        self.assertEqual(result["worker_projection_reason"],
                         "DISPOSABLE_HARNESS_SHAPE_ONLY")
        self.assertEqual(result["worker_harness_rows_shape_matched"], 3)
        self.assertEqual(result["physical_run_sequences"],
                         [1, 2, 4, 5, 6, 8, 9])
        self.assert_join_has_no_human_or_production_authority(result)

    def test_12_join_requires_source_and_all_ten_run_rows(self):
        rows = self.worker_projection()
        for candidate in (None, [], rows[:-1], rows + [copy.deepcopy(rows[-1])]):
            with self.subTest(length=None if candidate is None else len(candidate)):
                result = self.joined(candidate, seen=set())
                self.assertEqual(result["worker_projection_concordance"],
                                 "UNKNOWN")
                self.assertEqual(result["worker_projection_reason"],
                                 "MISSING_OR_EXTRA_RUN_EVENTS")
                self.assert_join_has_no_human_or_production_authority(result)
        result = self.joined(rows, seen=None)
        self.assertEqual(result["worker_projection_reason"],
                         "SOURCE_NOT_CONCORDANT")
        self.assert_join_has_no_human_or_production_authority(result)

    def test_13_worker_forged_allow_live_stage_and_eighth_source_rejected(self):
        changes = (
            (2, "decision", "ALLOW"),
            (6, "decision", "APPROVE"),
            (9, "decision", "APPROVE"),
            (9, "stage", "LIVE"),
            (9, "event_type", "OBSERVED"),
            (2, "source_event_id", self.receipt["events"][0]["source_event_id"]),
            (6, "event_key", "TEST_ONLY_FORGED_KEY"),
        )
        for index, key, value in changes:
            with self.subTest(index=index, key=key, value=value):
                rows = self.worker_projection()
                rows[index][key] = value
                result = self.joined(rows, seen=set())
                self.assertEqual(result["worker_projection_reason"],
                                 "UNTRUSTED_WORKER_STAGE_OR_APPROVAL")
                self.assert_join_has_no_human_or_production_authority(result)

    def test_14_source_physical_ordinal_and_core_hash_mismatch_rejected(self):
        changes = (
            (3, "source_event_id", "SYN-EVT-" + "A" * 20),
            (3, "event_key", "SYN-EVT-" + "A" * 20),
            (3, "payload_sha256", "a" * 64),
            (3, "full_event_sha256", "b" * 64),
            (7, "status", "BLOCKED"),
        )
        for index, key, value in changes:
            with self.subTest(index=index, key=key):
                rows = self.worker_projection()
                rows[index][key] = value
                result = self.joined(rows, seen=set())
                self.assertEqual(result["worker_projection_concordance"],
                                 "UNKNOWN")
                self.assertIn(result["worker_projection_reason"],
                              ("SOURCE_RUN_HASH_OR_ID_MISMATCH",
                               "FOREIGN_REPLAYED_OR_FORGED_RUN_ROW"))
                self.assert_join_has_no_human_or_production_authority(result)
        rows = self.worker_projection()
        rows[3]["sequence"] = 3
        self.assertEqual(self.joined(rows, seen=set())["worker_projection_reason"],
                         "FOREIGN_REPLAYED_OR_FORGED_RUN_ROW")

    def test_15_foreign_scope_duplicate_digest_and_extra_keys_rejected(self):
        for index, key, value in (
            (0, "tenant_id", "TEST_ONLY_FOREIGN_TENANT"),
            (4, "run_id", "TEST_ONLY_FOREIGN_RUN"),
            (9, "incident_id", "TEST_ONLY_FOREIGN_INCIDENT"),
            (9, "payload_sha256", self.worker_projection()[2]["payload_sha256"]),
            (9, "full_event_sha256", "not-a-sha"),
            (9, "untrusted_human_allow", True),
        ):
            with self.subTest(index=index, key=key):
                rows = self.worker_projection()
                rows[index][key] = value
                result = self.joined(rows, seen=set())
                self.assertEqual(result["worker_projection_reason"],
                                 "FOREIGN_REPLAYED_OR_FORGED_RUN_ROW")
                self.assert_join_has_no_human_or_production_authority(result)

    def test_16_replayed_or_revoked_source_never_validates_worker_join(self):
        rows, seen = self.worker_projection(), set()
        first = self.joined(rows, seen=seen)
        self.assertEqual(first["worker_projection_concordance"],
                         "CONSISTENT_UNTRUSTED")
        second = self.joined(rows, seen=seen)
        self.assertEqual(second["source_reason"], "REPLAYED_CORE_RECEIPT")
        self.assertEqual(second["worker_projection_reason"],
                         "SOURCE_NOT_CONCORDANT")
        self.assert_join_has_no_human_or_production_authority(second)
        self.setUp()
        forged = copy.deepcopy(self.receipt)
        forged["expires_at"] = self.NOW - 1
        forged["receipt_sha256"] = consumer._digest(
            consumer.RECEIPT_DOMAIN,
            {k: v for k, v in forged.items() if k != "receipt_sha256"})
        denied = self.joined(self.worker_projection(), seen=set(), receipt=forged)
        self.assertEqual(denied["source_concordance"], "UNKNOWN")
        self.assertEqual(denied["worker_projection_reason"],
                         "SOURCE_NOT_CONCORDANT")
        self.assert_join_has_no_human_or_production_authority(denied)



if __name__ == "__main__":
    unittest.main()
