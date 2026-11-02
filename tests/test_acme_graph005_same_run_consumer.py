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


    def test_17_nonanchor_unkeyed_receipt_cannot_attest_provenance(self):
        """Rehashing a non-anchor Core row is not independent signed evidence.

        An unkeyed checksum and a caller-supplied matching Worker projection
        can agree on substituted bytes. The consumer MUST remain untrusted.
        """
        for index, replace in ((2, False), (6, True)):
            with self.subTest(source_ordinal=index + 1, replace=replace):
                self.setUp()
                original_digest = self.receipt["receipt_sha256"]
                original_rows = self.worker_projection()
                source = self.receipt["events"][index]
                if replace:
                    source["payload_sha256"] = hashlib.sha256(
                        b"TEST_ONLY_SUBSTITUTED_NONANCHOR_PAYLOAD").hexdigest()
                    source["full_event_sha256"] = hashlib.sha256(
                        b"TEST_ONLY_SUBSTITUTED_NONANCHOR_FULL").hexdigest()
                else:
                    source["payload_sha256"], source["full_event_sha256"] = (
                        source["full_event_sha256"], source["payload_sha256"])
                self.sign_untrusted()
                self.assertNotEqual(self.receipt["receipt_sha256"], original_digest)

                # Unmodified Worker projection catches the changed Core row.
                mismatch = self.joined(original_rows, seen=set())
                self.assertEqual(mismatch["source_concordance"],
                                 "CONSISTENT_UNTRUSTED")
                self.assertEqual(mismatch["worker_projection_concordance"],
                                 "UNKNOWN")
                self.assertEqual(mismatch["worker_projection_reason"],
                                 "SOURCE_RUN_HASH_OR_ID_MISMATCH")
                self.assert_join_has_no_human_or_production_authority(mismatch)

                # A forged *matching* projection still cannot sign provenance.
                physical_index = consumer.PHYSICAL_SEQUENCES[index] - 1
                for field in ("payload_sha256", "full_event_sha256"):
                    original_rows[physical_index][field] = source[field]
                shape = self.joined(original_rows, seen=set())
                self.assertEqual(shape["source_concordance"],
                                 "CONSISTENT_UNTRUSTED")
                self.assertEqual(shape["worker_projection_concordance"],
                                 "CONSISTENT_UNTRUSTED")
                self.assertEqual(shape["core_https_runtime_authentication"],
                                 "NOT_ATTESTED")
                self.assertEqual(shape["durable_replay_fence"],
                                 "NOT_ATTESTED")
                self.assert_join_has_no_human_or_production_authority(shape)

                # Claiming a portable signature without one is rejected.
                self.receipt["portable_signature"] = "SIGNED"
                self.sign_untrusted()
                forged = self.joined(original_rows, seen=set())
                self.assertEqual(forged["source_concordance"], "UNKNOWN")
                self.assertEqual(forged["worker_projection_reason"],
                                 "SOURCE_NOT_CONCORDANT")
                self.assert_join_has_no_human_or_production_authority(forged)



    def vertical(self, rows=None, *, seen=None, receipt=None, claims=None,
                 glpi=None, evidence=None, candidate=None):
        from tools import acme_graph005_itil_15_stage_contract as vertical
        return vertical.consume(
            self.manifest,
            run_events=self.worker_projection() if rows is None else rows,
            receipt=self.receipt if receipt is None else receipt,
            claims=self.claims if claims is None else claims,
            expected=self.expected, record=self.record,
            source_issuer=self.source_issuer, now=self.NOW,
            seen_receipt_hashes=seen, glpi_receipt=glpi,
            evidence_receipt=evidence, stage_candidate=candidate)

    def assert_vertical_unexecuted(self, result):
        self.assertEqual(result["stage_count"], 15)
        self.assertEqual((result["verified_stage_count"],
                          result["not_executed_stage_count"]), (0, 15))
        self.assertEqual((result["verified_checkpoint_count"],
                          result["not_executed_checkpoint_count"]), (0, 6))
        self.assertTrue(all(row["status"] == "NOT_EXECUTED" and
                            row["verification"] == "UNKNOWN" and
                            row["runtime_id"] is None and
                            row["runtime_evidence_ids"] == []
                            for row in result["stages"]))
        self.assertTrue(all(row["status"] == "NOT_EXECUTED" and
                            row["id"] is None for row in result["checkpoints"]))
        self.assertEqual(result["glpi_human_allow"], "NOT_ATTESTED")
        self.assertEqual(result["hitl_approval"], "NOT_ATTESTED")
        self.assertEqual(result["core_pg16_authority"], "UNKNOWN")
        self.assertEqual(result["actor_idp_authority"], "UNKNOWN")
        self.assertEqual(result["core_terminal_014_joined"], "NOT_ATTESTED")
        self.assertEqual(result["core_outbox_replay_joined"], "NOT_ATTESTED")
        self.assertEqual(result["durable_replay_fence"], "NOT_ATTESTED")
        self.assertEqual(result["runtime_e2e"], "NOT_EXECUTED")
        self.assertIsNone(result["runtime_incident_id"])
        self.assertIsNone(result["runtime_run_id"])
        self.assertIsNone(result["runtime_ticket_id"])
        self.assertEqual(result["runtime_evidence_ids"], [])
        for key in ("simulation_executed", "post_action_verified",
                    "resolution_verified", "reopen_verified",
                    "publishable_to_core_or_glpi", "live_effects_authorized"):
            self.assertFalse(result[key])
        self.assertEqual(result["release_stable"], "NO_GO")
        rendered = json.dumps(result)
        for secret in ("TEST_ONLY_ACTOR_A", "TEST_ONLY_TENANT_A",
                       "TEST_ONLY_INCIDENT_A", "TEST_ONLY_RUN_A",
                       "TEST_ONLY_TICKET_A", "TEST_ONLY_EVIDENCE_1"):
            self.assertNotIn(secret, rendered)

    def test_18_fifteen_stage_same_run_source_anchor_is_not_runtime_proof(self):
        from tools import acme_synthetic_itil_stage_authority_consumer as plan
        result = self.vertical(seen=set())
        self.assertEqual(result["contract_status"], "CONSISTENT_UNTRUSTED")
        self.assertEqual(result["source_concordance"], "CONSISTENT_UNTRUSTED")
        self.assertEqual(result["worker_projection_concordance"],
                         "CONSISTENT_UNTRUSTED")
        self.assertEqual(result["source_ordinals"], list(range(1, 8)))
        self.assertEqual(result["physical_run_sequences"],
                         [1, 2, 4, 5, 6, 8, 9])
        self.assertEqual(result["twin_impact"]["candidate_ci_count"], 10)
        self.assertEqual(result["twin_impact"]["source_ci_id"],
                         "ACME-SAN-FABRIC-A")
        self.assertEqual(result["twin_impact"]["selected_service_id"],
                         "ACME-SVC-PAYMENTS")
        self.assertEqual(result["twin_impact"]["observed_service_impact"],
                         "UNKNOWN")
        expected_stages = plan.build_receipt(self.manifest)["stages"]
        self.assertEqual([s["stage"] for s in result["stages"]],
                         [s["stage"] for s in expected_stages])
        for projected, expected in zip(result["stages"], expected_stages):
            ordinal = expected["source_step"]
            core = self.receipt["events"][ordinal - 1]
            self.assertEqual(projected["source_event_id"],
                             expected["source_event_id"])
            self.assertEqual(projected["source_ordinal"], ordinal)
            self.assertEqual(projected["physical_run_sequence"],
                             consumer.PHYSICAL_SEQUENCES[ordinal - 1])
            self.assertEqual(projected["fixture_full_sha256"],
                             expected["acme_full_event_sha256"])
            self.assertEqual(projected["core_full_sha256_untrusted"],
                             core["full_event_sha256"])
            self.assertEqual(projected["core_payload_sha256_untrusted"],
                             core["payload_sha256"])
            self.assertNotEqual(projected["fixture_full_sha256"],
                                projected["core_full_sha256_untrusted"])
        self.assert_vertical_unexecuted(result)

    def test_19_missing_forged_or_eighth_same_run_never_executes_itil(self):
        cases = ("missing", "eighth", "foreign_tenant", "forged_worker_allow",
                 "source_hash", "no_guard")
        for case in cases:
            with self.subTest(case=case):
                self.setUp()
                rows = self.worker_projection()
                if case == "missing":
                    rows.pop()
                elif case == "eighth":
                    rows.append(copy.deepcopy(rows[-1]))
                elif case == "foreign_tenant":
                    self.receipt["tenant_id"] = "TEST_ONLY_FOREIGN_TENANT"
                    self.sign_untrusted()
                elif case == "forged_worker_allow":
                    rows[9]["decision"] = "ALLOW"
                elif case == "source_hash":
                    rows[3]["full_event_sha256"] = "a" * 64
                result = self.vertical(rows, seen=None if case == "no_guard"
                                       else set())
                self.assertEqual(result["contract_status"], "UNKNOWN")
                self.assertTrue(all(
                    row["core_full_sha256_untrusted"] is None and
                    row["core_payload_sha256_untrusted"] is None
                    for row in result["stages"]))
                self.assert_vertical_unexecuted(result)

    def test_20_forged_human_and_evidence_shapes_cannot_promote_itil(self):
        from tools import acme_synthetic_itil_stage_authority_consumer as plan
        forged_glpi = {"decision": "ALLOW", "human": True,
                       "ticket_id": "TEST_ONLY_FORGED_TICKET"}
        forged_evidence = {"status": "VERIFIED", "immutable": True,
                           "evidence_id": "TEST_ONLY_FORGED_EVIDENCE"}
        result = self.vertical(seen=set(), glpi=forged_glpi,
                               evidence=forged_evidence)
        self.assertEqual(result["glpi_receipt_shape"], "UNVERIFIED")
        self.assertEqual(result["evidence_receipt_shape"], "UNVERIFIED")
        self.assertEqual(result["contract_status"], "CONSISTENT_UNTRUSTED")
        self.assert_vertical_unexecuted(result)
        self.assertNotIn("TEST_ONLY_FORGED", json.dumps(result))
        candidate = plan.build_receipt(self.manifest)
        candidate["stages"][9]["status"] = "VERIFIED"
        with self.assertRaisesRegex(ValueError, "foreign, missing or promoted"):
            self.vertical(seen=set(), candidate=candidate)

    def test_21_rehashed_nonanchor_and_replay_remain_unexecuted(self):
        rows, seen = self.worker_projection(), set()
        first = self.vertical(rows, seen=seen)
        self.assertEqual(first["contract_status"], "CONSISTENT_UNTRUSTED")
        replayed = self.vertical(rows, seen=seen)
        self.assertEqual(replayed["contract_status"], "UNKNOWN")
        self.assertEqual(replayed["source_reason"], "REPLAYED_CORE_RECEIPT")
        self.assert_vertical_unexecuted(replayed)
        self.setUp()
        rows = self.worker_projection()
        source = self.receipt["events"][6]  # ordinal 7 / physical Run 9
        source["payload_sha256"] = hashlib.sha256(
            b"TEST_ONLY_FORGED_PAYLOAD").hexdigest()
        source["full_event_sha256"] = hashlib.sha256(
            b"TEST_ONLY_FORGED_FULL").hexdigest()
        self.sign_untrusted()  # unkeyed digest is not a signature
        rows[8]["payload_sha256"] = source["payload_sha256"]
        rows[8]["full_event_sha256"] = source["full_event_sha256"]
        forged = self.vertical(rows, seen=set())
        self.assertEqual(forged["contract_status"], "CONSISTENT_UNTRUSTED")
        self.assert_vertical_unexecuted(forged)
        self.assertEqual(forged["source_provenance"], "NONPORTABLE_SHAPE_ONLY")


    @staticmethod
    def sign_unkeyed_ci_receipt(document, field):
        """Producer-format SHA256 integrity; not an actor or source signature."""
        document[field] = hashlib.sha256(json.dumps(
            {k: v for k, v in document.items() if k != field},
            sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def ci_artifact_pair(self):
        """Synthetic copies of two distinct disposable CI artifacts, no auth."""
        from tools import acme_graph005_ci_artifact_join as join
        head = "1fd6391f8a8e7129246ec1b9e4a0d6d4c4eed688"
        core = {
            "schema": "aiops.core-graph005-seven-015-source-receipt.v1",
            "source_head": head, "graph_version": join.GRAPH,
            "source_fixture_only": True, "same_run_readback": "PASS_SYNTHETIC_ONLY",
            "transport": "DISPOSABLE_TLS_BASIC_BOUND", "portable_signature": "NONE",
            "decision": "UNKNOWN", "link_status": "UNKNOWN",
            "human_glpi_attested": False, "acme_full_event_equivalence": "NOT_VERIFIED",
            "hash_domains": dict(join.DOMAINS),
            "source_payload_sequence_domain": "PINNED_SOURCE_ORDINAL",
            "source_run_sequence_domain": "PHYSICAL_RUN_SEQUENCE",
            "source_payload_ordinals": list(range(1, 8)),
            "source_run_sequences": list(join.PHYSICAL), "same_run_source_count": 7,
            "events": [{"source_event_id": sid, "pinned_source_ordinal": i + 1,
                        "physical_run_sequence": join.PHYSICAL[i],
                        "core_pg16_full_event_sha256": hashlib.sha256(
                            ("full-" + str(i)).encode()).hexdigest(),
                        "core_pg16_payload_sha256": hashlib.sha256(
                            ("payload-" + str(i)).encode()).hexdigest()}
                       for i, sid in enumerate(join.SOURCE_IDS)],
        }
        worker = {
            "schema": "aiops.worker-graph005-two-os-negative.v1",
            "source_head": head, "source_ids": list(join.SOURCE_IDS),
            "source_ordinals": list(range(1, 8)),
            "source_physical_sequences": list(join.PHYSICAL),
            "worker_os_processes": 2, "distinct_pids": True, "pg_major": 16,
            "verification": "UNVERIFIED", "human_glpi_attested": False,
            "portable_signature": "NONE", "execution_allowed": False,
            "effect_allowed": False, "effect_receipts": 0, "approve_count": 0,
            "temporal_signal_count": 0, "core_terminal_014_exercised": False,
            "core_outbox_replay_exercised": False,
            "source_after_revocation": "UNKNOWN",
            "reopen": "RECOMMENDED_NOT_EXECUTED",
        }
        self.sign_unkeyed_ci_receipt(core, "receipt_sha256")
        self.sign_unkeyed_ci_receipt(worker, "payload_sha256")
        return core, worker, head

    def test_22_cross_artifact_shape_never_promotes_itil_or_human(self):
        from tools import acme_graph005_ci_artifact_join as join
        core, worker, head = self.ci_artifact_pair()
        result = join.build_receipt(core, worker, head)
        self.assertEqual(result["cross_artifact_concordance"], "CONSISTENT_UNTRUSTED")
        self.assertEqual(result["independent_core_worker_same_run"], "NOT_ATTESTED")
        self.assertEqual(result["independent_actor_tenant_incident_run"], "NOT_ATTESTED")
        self.assertEqual(result["core_014_terminal_worker_join"], "NOT_ATTESTED")
        self.assertEqual((result["stage_count"], result["verified_stage_count"],
                          result["not_executed_stage_count"]), (15, 0, 15))
        self.assertEqual((result["checkpoint_count"], result["verified_checkpoint_count"],
                          result["not_executed_checkpoint_count"]), (6, 0, 6))
        self.assertEqual(result["twin_impact"]["candidate_impacted_ci_count"], 10)
        self.assertEqual(result["physical_run_sequences"], [1, 2, 4, 5, 6, 8, 9])
        self.assertFalse(result["publishable_to_core_or_glpi"])
        self.assertFalse(result["live_effects_authorized"])
        self.assertEqual(result["release_stable"], "NO_GO")

    def test_23_cross_artifact_nine_mutations_rejected(self):
        from tools import acme_graph005_ci_artifact_join as join
        core, worker, head = self.ci_artifact_pair()
        cases = join.negative_controls(core, worker, head)
        self.assertEqual(len(cases), 9)
        self.assertTrue(all(x["verdict"] == "REJECTED" for x in cases))

    def test_24_cross_artifact_foreign_head_does_not_authenticate_run(self):
        from tools import acme_graph005_ci_artifact_join as join
        core, worker, head = self.ci_artifact_pair()
        worker["source_head"] = "a" * 40
        result = join.build_receipt(core, worker, head)
        self.assertEqual(result["cross_artifact_concordance"], "UNKNOWN")
        self.assertEqual(result["cross_artifact_reason"],
                         "CROSS_ARTIFACT_EXACT_HEAD_MISMATCH")
        self.assertEqual(result["not_executed_stage_count"], 15)
        self.assertEqual(result["not_executed_checkpoint_count"], 6)
        self.assertIsNone(result["runtime_run_id"])

    def test_25_cross_artifact_zip_sha256_and_duplicate_json_rejected(self):
        import tempfile
        import zipfile
        from pathlib import Path
        from tools import acme_graph005_ci_artifact_join as join
        core, _, head = self.ci_artifact_pair()
        data = json.dumps(core, sort_keys=True).encode()
        digest = hashlib.sha256(data).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "receipt.zip"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr(join.CORE_FILE, data)
                z.writestr("core-graph005-seven-015.sha256",
                           digest + "  " + join.CORE_FILE + "\n")
            parsed, meta = join.read_artifact(path, join.CORE_FILE)
            self.assertEqual(parsed["source_head"], head)
            self.assertTrue(meta["sha256_sidecar_verified"])
            with zipfile.ZipFile(path, "w") as z:
                z.writestr(join.CORE_FILE, b'{"x":1,"x":2}')
                z.writestr("core-graph005-seven-015.sha256",
                           "a" * 64 + "  " + join.CORE_FILE)
            with self.assertRaisesRegex(ValueError, "SHA256 sidecar mismatch"):
                join.read_artifact(path, join.CORE_FILE)
            bad = b'{"x":1,"x":2}'
            with zipfile.ZipFile(path, "w") as z:
                z.writestr(join.CORE_FILE, bad)
                z.writestr("core-graph005-seven-015.sha256",
                           hashlib.sha256(bad).hexdigest() + "  " + join.CORE_FILE)
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                join.read_artifact(path, join.CORE_FILE)


    def test_26_rehashed_cross_artifact_nonanchor_cannot_attest_same_run(self):
        """A valid rehashed ZIP sidecar and matching claims are not signatures.

        Core and Worker CI artifacts can share a HEAD and graph without a
        cryptographically authenticated common Incident/Run or human IdP.
        """
        import tempfile
        import zipfile
        from pathlib import Path
        from tools import acme_graph005_ci_artifact_join as join

        core, worker, head = self.ci_artifact_pair()
        original_full = core["events"][2]["core_pg16_full_event_sha256"]
        core["events"][2]["core_pg16_full_event_sha256"] = hashlib.sha256(
            b"TEST_ONLY_REHASHED_NONANCHOR_CORE_FULL").hexdigest()
        self.assertNotEqual(
            core["events"][2]["core_pg16_full_event_sha256"], original_full)
        # These self-declared claims must never become independent authority.
        core["same_run_authenticated"] = True
        core["actor_idp_signature"] = "TEST_ONLY_FORGED_IDP_SIGNATURE"
        worker["same_run_authenticated"] = True
        worker["human_glpi_allow"] = True
        # A rehashed inner producer digest plus ZIP sidecar remains unkeyed.
        self.sign_unkeyed_ci_receipt(core, "receipt_sha256")
        self.sign_unkeyed_ci_receipt(worker, "payload_sha256")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "core.zip"
            data = json.dumps(core, sort_keys=True).encode()
            with zipfile.ZipFile(path, "w") as z:
                z.writestr(join.CORE_FILE, data)
                z.writestr("core-graph005-seven-015.sha256",
                           hashlib.sha256(data).hexdigest() + "  " +
                           join.CORE_FILE + "\n")
            parsed, meta = join.read_artifact(path, join.CORE_FILE)
            self.assertTrue(meta["sha256_sidecar_verified"])
            self.assertEqual(parsed["events"][2]["core_pg16_full_event_sha256"],
                             core["events"][2]["core_pg16_full_event_sha256"])

        receipt = join.build_receipt(parsed, worker, head, core_artifact=meta)
        self.assertEqual(receipt["cross_artifact_concordance"],
                         "CONSISTENT_UNTRUSTED")
        self.assertEqual(receipt["independent_core_worker_same_run"],
                         "NOT_ATTESTED")
        self.assertEqual(receipt["independent_actor_tenant_incident_run"],
                         "NOT_ATTESTED")
        self.assertEqual(receipt["core_https_runtime_authentication"],
                         "NOT_ATTESTED")
        self.assertEqual(receipt["portable_signature"], "NONE")
        self.assertEqual(receipt["glpi_human_allow"], "NOT_ATTESTED")
        self.assertEqual(receipt["hitl_approval"], "NOT_ATTESTED")
        self.assertEqual(receipt["stage_count"], 15)
        self.assertEqual((receipt["verified_stage_count"],
                          receipt["not_executed_stage_count"]), (0, 15))
        self.assertEqual((receipt["verified_checkpoint_count"],
                          receipt["not_executed_checkpoint_count"]), (0, 6))
        self.assertTrue(all(s["status"] == "NOT_EXECUTED" and
                            s["verification"] == "UNKNOWN" and
                            s["runtime_id"] is None
                            for s in receipt["stages"]))
        self.assertEqual(receipt["twin_impact"]["candidate_impacted_ci_count"], 10)
        self.assertEqual(receipt["twin_impact"]["observed_impact"], "UNKNOWN")
        self.assertEqual(receipt["runtime_e2e"], "NOT_EXECUTED")
        self.assertFalse(receipt["publishable_to_core_or_glpi"])
        self.assertFalse(receipt["live_effects_authorized"])
        self.assertEqual(receipt["release_stable"], "NO_GO")
        self.assertNotIn("TEST_ONLY_FORGED_IDP_SIGNATURE", json.dumps(receipt))

        # Even with matching HEAD, a claimed portable signature is invalid.
        parsed["portable_signature"] = "SIGNED"
        rejected = join.build_receipt(parsed, worker, head)
        self.assertEqual(rejected["cross_artifact_concordance"], "UNKNOWN")
        self.assertEqual(rejected["cross_artifact_reason"],
                         "UNTRUSTED_CORE_AUTHORITY_PROMOTION")
        self.assertEqual(rejected["not_executed_stage_count"], 15)
        self.assertEqual(rejected["not_executed_checkpoint_count"], 6)


    def test_27_inner_core_worker_receipt_digest_required_not_authority(self):
        """ZIP integrity cannot mask stale producer digests; rehash is not auth."""
        from tools import acme_graph005_ci_artifact_join as join
        core, worker, head = self.ci_artifact_pair()
        self.assertEqual(join.build_receipt(core, worker, head)[
            "cross_artifact_concordance"], "CONSISTENT_UNTRUSTED")
        for owner in ("core", "worker"):
            with self.subTest(owner=owner):
                c, w = copy.deepcopy(core), copy.deepcopy(worker)
                if owner == "core":
                    c["events"][2]["core_pg16_full_event_sha256"] = hashlib.sha256(
                        b"TEST_ONLY_REHASHED_NONANCHOR").hexdigest()
                    changed, digest_field = c, "receipt_sha256"
                else:
                    w["test_only_unkeyed_marker"] = "TEST_ONLY_NOT_AN_ATTESTATION"
                    changed, digest_field = w, "payload_sha256"
                stale = join.build_receipt(c, w, head)
                self.assertEqual(stale["cross_artifact_concordance"], "UNKNOWN")
                self.assertEqual(stale["cross_artifact_reason"],
                                 "CORRUPT_OR_MISSING_INNER_RECEIPT_DIGEST")
                self.assertEqual(stale["verified_stage_count"], 0)
                self.assertEqual(stale["verified_checkpoint_count"], 0)
                self.sign_unkeyed_ci_receipt(changed, digest_field)
                rehashed = join.build_receipt(c, w, head)
                self.assertEqual(rehashed["cross_artifact_concordance"],
                                 "CONSISTENT_UNTRUSTED")
                self.assertEqual(rehashed["independent_core_worker_same_run"],
                                 "NOT_ATTESTED")
                self.assertEqual(rehashed["glpi_human_allow"], "NOT_ATTESTED")
                self.assertEqual(rehashed["hitl_approval"], "NOT_ATTESTED")
                self.assertEqual(rehashed["not_executed_stage_count"], 15)
                self.assertEqual(rehashed["not_executed_checkpoint_count"], 6)
                self.assertFalse(rehashed["live_effects_authorized"])


    def test_28_terminal_014_cross_head_without_015_stays_unexecuted(self):
        """A real Worker terminal 014 test with zero 015 rows cannot join ACME.

        Core graph005 SOURCE CI and Worker terminal recovery CI are independent
        processes/heads. Even a valid unkeyed Worker digest and canonical
        Incident-shaped fields do not establish a shared 015 writer or IdP.
        """
        from tools import acme_graph005_ci_artifact_join as join

        core, worker, head = self.ci_artifact_pair()
        worker.update({
            "source_head": "653033bb02b721bd0f4ce90d64d95a4d83a1c4ea",
            "core_terminal_014_exercised": True,
            "core_pg16_run_event_count": 0,
            "same_run_015_event_writer_joined": False,
            "incident_id": "TEST_ONLY_UNTRUSTED_INCIDENT",
            "run_id": "TEST_ONLY_UNTRUSTED_RUN",
        })
        self.sign_unkeyed_ci_receipt(worker, "payload_sha256")
        foreign = join.build_receipt(core, worker, head)
        self.assertEqual(foreign["cross_artifact_concordance"], "UNKNOWN")
        self.assertEqual(foreign["cross_artifact_reason"],
                         "CROSS_ARTIFACT_EXACT_HEAD_MISMATCH")

        # Even an attacker re-pinning the Worker claim to the Core CI HEAD
        # cannot turn a separate 014 terminal receipt into 015 SOURCE proof.
        worker["source_head"] = head
        self.sign_unkeyed_ci_receipt(worker, "payload_sha256")
        re_pinned = join.build_receipt(core, worker, head)
        self.assertEqual(re_pinned["cross_artifact_concordance"], "UNKNOWN")
        self.assertEqual(re_pinned["cross_artifact_reason"],
                         "UNTRUSTED_WORKER_OR_HUMAN_AUTHORITY_PROMOTION")
        for result in (foreign, re_pinned):
            self.assertEqual((result["verified_stage_count"],
                              result["not_executed_stage_count"]), (0, 15))
            self.assertEqual((result["verified_checkpoint_count"],
                              result["not_executed_checkpoint_count"]), (0, 6))
            self.assertEqual(result["independent_core_worker_same_run"],
                             "NOT_ATTESTED")
            self.assertEqual(result["core_014_terminal_worker_join"],
                             "NOT_ATTESTED")
            self.assertEqual(result["glpi_human_allow"], "NOT_ATTESTED")
            self.assertEqual(result["hitl_approval"], "NOT_ATTESTED")
            self.assertIsNone(result["runtime_incident_id"])
            self.assertIsNone(result["runtime_run_id"])
            self.assertFalse(result["live_effects_authorized"])
            self.assertEqual(result["release_stable"], "NO_GO")
            self.assertNotIn("TEST_ONLY_UNTRUSTED", json.dumps(result))


    def test_29_debian_nine_anonymous_gets_never_grant_glpi_or_itil(self):
        """Strict healthy :7777 plus 6x401 is not an authenticated ACME Run.

        Mirrors the redacted 2026-11-02 15:37Z host contract shape; fixture
        is synthetic and never claims independent host/IdP/GLPI authority.
        """
        from tools import acme_graph005_ci_artifact_join as join

        core, worker, head = self.ci_artifact_pair()
        image = "sha256:" + "a" * 64
        sidecar = {
            "schema": "aiops.debian-poller-qualification.v1",
            "portal": {"image_id": image, "state": "running",
                       "health": "healthy",
                       "bindings": [{"host_ip": "0.0.0.0", "host_port": 7777}]},
            "deployment_preflight": {
                "deployed_image_id": image, "portal_env_port_7777": True,
                "portal_host_port_7777": True,
                "verdict": "DEPLOYED_HEALTH_PASS_E2E_PENDING"},
            "portal_nine_readonly_contracts": {
                "image_id": image, "status": "PASS_READONLY_ONLY",
                "total": 9, "passed": 9,
                "acme_e2e": "BLOCKED_NO_INDEPENDENT_HUMAN_GLPI_IDP_AUTHORITY",
                "incident_id": None, "run_id": None, "glpi_ticket_id": None,
                "checks": [
                    {"name": name, "path": path, "http_status": status,
                     "status": "PASS"}
                    for name, path, status in join.HOST_ANONYMOUS_CONTRACTS]},
            "http_7777": {"status": 200, "qualified": True},
            "external_tls_sso_glpi_e2e": "NOT_VERIFIED",
            "release_stable": "NO_GO",
        }
        receipt = join.build_receipt(core, worker, head, host_sidecar=sidecar)
        host = receipt["portal_host_readonly"]
        self.assertEqual(host["classification"], "CONSISTENT_UNTRUSTED")
        self.assertEqual(host["anonymous_gets_shape_matched"], 9)
        self.assertEqual(host["human_idp_glpi_authority"], "NOT_ATTESTED")
        self.assertEqual(host["independent_core_worker_same_run"], "NOT_ATTESTED")
        self.assertEqual((receipt["verified_stage_count"],
                          receipt["not_executed_stage_count"]), (0, 15))
        self.assertEqual((receipt["verified_checkpoint_count"],
                          receipt["not_executed_checkpoint_count"]), (0, 6))
        self.assertEqual(receipt["glpi_human_allow"], "NOT_ATTESTED")
        self.assertIsNone(receipt["runtime_run_id"])
        self.assertEqual(receipt["runtime_e2e"], "NOT_EXECUTED")

        for mutation in ("fake_glpi_200", "fake_run", "wrong_image",
                         "compose_mismatch", "fake_release_go",
                         "missing_denied_route"):
            with self.subTest(mutation=mutation):
                forged = copy.deepcopy(sidecar)
                contracts = forged["portal_nine_readonly_contracts"]
                if mutation == "fake_glpi_200":
                    contracts["checks"][6]["http_status"] = 200
                elif mutation == "fake_run":
                    contracts["run_id"] = "TEST_ONLY_FORGED_RUN"
                elif mutation == "wrong_image":
                    contracts["image_id"] = "sha256:" + "b" * 64
                elif mutation == "compose_mismatch":
                    forged["deployment_preflight"]["portal_env_port_7777"] = False
                elif mutation == "fake_release_go":
                    forged["release_stable"] = "GO"
                elif mutation == "missing_denied_route":
                    contracts["checks"].pop()
                result = join.build_receipt(core, worker, head,
                                            host_sidecar=forged)
                self.assertEqual(result["portal_host_readonly"]["classification"],
                                 "UNKNOWN")
                self.assertEqual(result["portal_host_readonly"][
                    "anonymous_gets_shape_matched"], 0)
                self.assertEqual(result["not_executed_stage_count"], 15)
                self.assertEqual(result["not_executed_checkpoint_count"], 6)
                self.assertEqual(result["glpi_human_allow"], "NOT_ATTESTED")
                self.assertEqual(result["release_stable"], "NO_GO")
                self.assertNotIn("TEST_ONLY_FORGED_RUN", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
