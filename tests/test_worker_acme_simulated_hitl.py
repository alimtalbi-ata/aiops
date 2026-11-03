import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import ast
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from worker.acme_simulated_hitl import (
    ISSUER, SandboxDenied, capability, canonical_source_ids, simulate_no_effect,
    receipt_digest_valid, validated_service_origin,
    validate_intent, validate_readbacks,
)

NOW = datetime(2026, 11, 2, 16, 0, tzinfo=timezone.utc)
INTENT = {
    "attempt_id": "ACME-SIM-TEST-001", "tenant_id": "ACME-TEST",
    "scenario_id": "ACME-SAN-PAYMENTS", "mode": "SIMULATION",
    "approval_issuer": ISSUER, "incident_id": "INC-TEST-001",
    "run_id": "RUN-TEST-001", "proposal_id": "PROP-TEST-001",
    "approval_id": "SIM-APP-TEST-001", "ticket_id": "SIM-GLPI-TEST-001",
    "idempotency_key": "ACME-SIM-TEST-001",
    "human_approved": False, "execution_allowed": False,
    "effect_allowed": False,
}


def fixtures():
    common = dict(attempt_id=INTENT["attempt_id"], tenant_id="ACME-TEST",
                  incident_id=INTENT["incident_id"], run_id=INTENT["run_id"])
    core = dict(common, scenario_id="ACME-SAN-PAYMENTS",
                mode="SIMULATION", approval_issuer=ISSUER,
                glpi_mode="SIMULATED_ONLY", human_approval_claimed=False,
                incident_status="PREPARED", run_status="PREPARED",
                ticket_id=INTENT["ticket_id"], ticket_authority="SIMULATED_ONLY",
                ticket_status="PREPARED", source="SYNTHETIC_SIMULATOR",
                source_event_count=7, source_hashes_qualified=True,
                source_event_ids=canonical_source_ids(INTENT["attempt_id"]),
                request_sha256="a" * 64,
                human_approved=False, execution_allowed=False,
                effect_allowed=False, live_effects_allowed=False,
                real_glpi_writes_allowed=False,
                analysis_validated=True, critic_validated=True, evidence_count=2,
                proposal_id=INTENT["proposal_id"])
    twin = dict(common, scenario_id="ACME-SAN-PAYMENTS",
                resolution_verified=False,
                post_resolution_readback_required=True,
                approval_id=INTENT["approval_id"],
                proposal_id=INTENT["proposal_id"], ticket_id=INTENT["ticket_id"],
                issuer_id="twin-acme-test", approval_issuer=ISSUER,
                approval_actor=ISSUER, approval_kind="SIMULATED",
                approval_status="SIMULATED", mode="SIMULATION",
                human_approved=False, execution_allowed=False,
                effect_allowed=False, live_effects_allowed=False,
                real_glpi_writes_allowed=False,
                impact_root="ACME-SAN-FABRIC-A",
                impacted_cis=["ACME-SVC-PAYMENTS"],
                approval_phase="PRE_RESOLUTION",
                core_status_at_issuance="PREPARED",
                core_request_sha256=core["request_sha256"],
                core_source_event_ids=list(core["source_event_ids"]),
                approval_nonce="NONCE-TEST-001",
                issued_at=(NOW-timedelta(seconds=30)).isoformat(),
                expires_at=(NOW+timedelta(minutes=2)).isoformat())
    policy = dict(common, state="PASS", human_approval_claimed=False,
                  decision="SIMULATE", approval_kind="SIMULATED",
                  approval_issuer=ISSUER, mode="SIMULATION",
                  human_approved=False, execution_allowed=False,
                  effect_allowed=False, live_effects_allowed=False,
                  real_glpi_writes_allowed=False,
                  proposal_id=INTENT["proposal_id"], ticket_id=INTENT["ticket_id"],
                  approval_id=INTENT["approval_id"])
    return dict(core=core, twin=twin, policy=policy)


class AcmeSimulatedHitlTests(unittest.TestCase):
    def test_01_strict_positive_no_effect_two_independent_reads(self):
        docs = fixtures()
        calls = []
        async def get(component, path):
            calls.append((component, path))
            return deepcopy(docs[component])
        result = asyncio.run(simulate_no_effect(INTENT, get=get, now=NOW))
        self.assertEqual(len(calls), 6)
        self.assertEqual({c for c, _ in calls}, {"core", "twin", "policy"})
        self.assertTrue(all(path.endswith(INTENT["attempt_id"]) for _, path in calls))
        self.assertEqual(result["receipt_status"], "SIMULATED_NO_EFFECT")
        self.assertEqual(len(result["audit_transitions"]), 4)
        self.assertEqual(result["audit_transitions"][0], "CORE_PREPARED_INDEPENDENTLY_VERIFIED")
        self.assertEqual(result["audit_transitions"][-1], "WORKER_NO_EFFECT")
        self.assertEqual(result["receipt_phase"], "PRE_RESOLUTION")
        self.assertEqual(result["core_status_at_validation"], "PREPARED")
        self.assertFalse(result["resolution_verified"])
        self.assertTrue(result["post_resolution_readback_required"])
        self.assertEqual(result["audit_authority"], "TEMPORAL_WORKFLOW_HISTORY_ONLY")
        self.assertFalse(result["human_approved"])
        self.assertFalse(result["execution_allowed"])
        self.assertFalse(result["effect_allowed"])
        self.assertFalse(result["glpi_write"])
        self.assertEqual(result["effect_receipts"], 0)
        self.assertNotIn("approval_nonce", result)

    def test_02_cross_tenant_denied_before_transport(self):
        for tenant in ("TENANT-FOREIGN", "", None):
            bad = dict(INTENT, tenant_id=tenant)
            with self.subTest(tenant=tenant), self.assertRaises(SandboxDenied):
                validate_intent(bad)
        docs = fixtures()
        docs["twin"]["tenant_id"] = "TENANT-FOREIGN"
        with self.assertRaises(SandboxDenied):
            validate_readbacks(INTENT, **docs, now=NOW)

    def test_03_wrong_issuer_or_forged_human_allow(self):
        for key, value in (
            ("approval_issuer", "GLPI_HUMAN"), ("approval_actor", "human-user"),
            ("approval_kind", "HUMAN"), ("human_approved", True),
            ("approval_status", "ALLOW"),
        ):
            docs = fixtures()
            docs["twin"][key] = value
            with self.subTest(key=key), self.assertRaises(SandboxDenied):
                validate_readbacks(INTENT, **docs, now=NOW)
        bad = dict(INTENT, approval_issuer="GLPI_HUMAN")
        with self.assertRaises(SandboxDenied):
            validate_intent(bad)

    def test_04_expired_future_or_overlong_approval_denied(self):
        for issued, expires in (
            (NOW-timedelta(minutes=6), NOW-timedelta(seconds=1)),
            (NOW+timedelta(minutes=2), NOW+timedelta(minutes=3)),
            (NOW-timedelta(minutes=1), NOW+timedelta(minutes=8)),
            (NOW-timedelta(minutes=2), NOW-timedelta(minutes=1)),
        ):
            docs = fixtures()
            docs["twin"]["issued_at"] = issued.isoformat()
            docs["twin"]["expires_at"] = expires.isoformat()
            with self.subTest(issued=issued, expires=expires), self.assertRaises(SandboxDenied):
                validate_readbacks(INTENT, **docs, now=NOW)

    def test_05_replay_or_approval_rotation_denied(self):
        docs = fixtures()
        count = 0
        async def get(component, path):
            nonlocal count
            count += 1
            result = deepcopy(docs[component])
            if count > 3 and component == "twin":
                result["approval_nonce"] = "NONCE-OTHER-001"
            return result
        with self.assertRaises(SandboxDenied):
            asyncio.run(simulate_no_effect(INTENT, get=get, now=NOW))
        self.assertEqual(count, 6)

    def test_06_live_and_effect_permissions_denied(self):
        for key, value in (
            ("mode", "LIVE"), ("execution_allowed", True),
            ("effect_allowed", True), ("human_approved", True),
        ):
            with self.subTest(key=key), self.assertRaises(SandboxDenied):
                validate_intent(dict(INTENT, **{key: value}))
        for component, key, value in (
            ("twin", "live_effects_allowed", True),
            ("twin", "real_glpi_writes_allowed", True),
            ("policy", "effect_allowed", True),
            ("policy", "human_approved", True),
        ):
            docs = fixtures()
            docs[component][key] = value
            with self.subTest(component=component, key=key), self.assertRaises(SandboxDenied):
                validate_readbacks(INTENT, **docs, now=NOW)

    def test_07_idempotency_and_extra_token_denied(self):
        for changes in (
            {"idempotency_key": "REPLAY-NEW-001"},
            {"lease_token": "should-not-enter-history"},
            {"attempt_id": "bad/slash"},
            {"ticket_id": "GLPI-REAL-001"},
            {"approval_id": "APP-HUMAN-001"},
        ):
            with self.subTest(changes=list(changes)), self.assertRaises(SandboxDenied):
                validate_intent(dict(INTENT, **changes))

    def test_08_core_resolution_and_id_mismatch_denied(self):
        for key, value in (
            ("run_status", "RUNNING"), ("run_status", "RESOLVED"),
            ("incident_status", "OPEN"), ("incident_status", "RESOLVED"),
            ("ticket_status", "RESOLVED"), ("source_event_count", 6),
            ("source_hashes_qualified", False), ("human_approved", True),
            ("ticket_authority", "GLPI_REAL"), ("source", "REAL"),
            ("evidence_count", 1), ("critic_validated", False),
            ("proposal_id", "PROP-OTHER-001"), ("incident_id", "INC-FOREIGN"),
        ):
            docs = fixtures()
            docs["core"][key] = value
            with self.subTest(key=key), self.assertRaises(SandboxDenied):
                validate_readbacks(INTENT, **docs, now=NOW)

    def test_09_policy_simulate_binding_required(self):
        for key, value in (
            ("decision", "ALLOW"), ("approval_kind", "HUMAN"),
            ("approval_issuer", "IDP"), ("approval_id", "SIM-APP-FOREIGN"),
            ("proposal_id", "PROP-FOREIGN"), ("mode", "LIVE"),
        ):
            docs = fixtures()
            docs["policy"][key] = value
            with self.subTest(key=key), self.assertRaises(SandboxDenied):
                validate_readbacks(INTENT, **docs, now=NOW)

    def test_10_transport_denial_is_sanitized_and_no_receipt(self):
        for status in (401, 403, 503):
            async def get(component, path):
                raise RuntimeError("HTTP " + str(status) + " bearer secret")
            with self.subTest(status=status), self.assertRaisesRegex(
                    SandboxDenied, "^sandbox_independent_readback_unavailable$"):
                asyncio.run(simulate_no_effect(INTENT, get=get, now=NOW))

    def test_11_capability_is_simulated_only(self):
        cap = capability()
        self.assertEqual(cap["component"], "worker")
        self.assertEqual(cap["approval_issuer"], ISSUER)
        self.assertEqual(cap["tenant_id"], "ACME-TEST")
        self.assertFalse(cap["human_approval_claimed"])
        self.assertFalse(cap["live_effects_allowed"])
        self.assertFalse(cap["real_glpi_writes_allowed"])

    def test_12_registered_production_worker_and_temporal_no_effect(self):
        main = (ROOT / "app/worker/main.py").read_text()
        flows = (ROOT / "app/worker/temporal_workflows.py").read_text()
        tree = ast.parse(main)
        worker = next(n for n in ast.walk(tree)
                      if isinstance(n, ast.AsyncFunctionDef) and n.name == "worker_main")
        self.assertIn("acme_simulated_no_effect", ast.unparse(worker))
        self.assertIn("AcmeSimulatedHitlWorkflow", ast.unparse(worker))
        self.assertIn("REJECT_DUPLICATE", main)
        self.assertIn("/api/sandbox/acme/e2e", main)
        self.assertIn("acme_simulated_no_effect", flows)
        self.assertNotIn("signal_workflow", flows)
        self.assertNotIn("shared.http", flows)


    def test_13_resolution_before_worker_receipt_is_forbidden(self):
        # PREPARED -> Twin SIMULATED -> Policy SIMULATE -> Worker no-effect
        # -> Core RESOLVED is the only permissible causal order.
        for component, field in (
            ("core", "incident_status"), ("core", "run_status"),
            ("core", "ticket_status"),
        ):
            docs = fixtures()
            docs[component][field] = "RESOLVED"
            with self.subTest(field=field), self.assertRaises(SandboxDenied):
                validate_readbacks(INTENT, **docs, now=NOW)

    def test_14_transition_to_resolved_between_independent_reads_denied(self):
        docs = fixtures()
        order = []
        async def get(component, path):
            order.append(component)
            result = deepcopy(docs[component])
            if len(order) > 3 and component == "core":
                result["run_status"] = "RESOLVED"
            return result
        with self.assertRaises(SandboxDenied):
            asyncio.run(simulate_no_effect(INTENT, get=get, now=NOW))
        self.assertEqual(order, ["core", "twin", "policy", "core", "twin", "policy"])

    def test_15_immutable_source_and_policy_rotation_denied(self):
        for component, field, changed in (
            ("core", "source_event_ids", ["SYN-EVT-OTHER"]),
            ("core", "request_sha256", "SHA256-REBOUND"),
            ("policy", "decision", "REJECT"),
            ("twin", "approval_id", "SIM-APP-REBOUND"),
        ):
            docs = fixtures()
            seen = 0
            async def get(which, path):
                nonlocal seen
                seen += 1
                result = deepcopy(docs[which])
                if seen > 3 and which == component:
                    result[field] = changed
                return result
            with self.subTest(component=component, field=field), self.assertRaises(SandboxDenied):
                asyncio.run(simulate_no_effect(INTENT, get=get, now=NOW))

    def test_16_signed_twin_identity_and_ticket_binding(self):
        for component, field, changed in (
            ("twin", "issuer_id", "fake-issuer"),
            ("twin", "ticket_id", "SIM-GLPI-FOREIGN"),
            ("policy", "ticket_id", "SIM-GLPI-FOREIGN"),
            ("core", "live_effects_allowed", True),
        ):
            docs = fixtures()
            docs[component][field] = changed
            with self.subTest(component=component, field=field), self.assertRaises(SandboxDenied):
                validate_readbacks(INTENT, **docs, now=NOW)

    def test_17_temporal_receipt_does_not_claim_core_resolution(self):
        docs = fixtures()
        async def get(component, path):
            return deepcopy(docs[component])
        receipt = asyncio.run(simulate_no_effect(INTENT, get=get, now=NOW))
        self.assertNotIn("CORE_RESOLVED_INDEPENDENTLY_VERIFIED", receipt["audit_transitions"])
        self.assertFalse(receipt["resolution_verified"])
        self.assertFalse(receipt["glpi_write"])
        self.assertEqual(receipt["effect_receipts"], 0)
        self.assertNotIn("approval_nonce", receipt)
        # The Core-only final RESOLVED readback must be performed *later*
        # by the orchestrator, never manufactured by this Worker activity.


    def test_18_twin_approval_must_bind_exact_core_prepared_snapshot(self):
        for field, value in (
            ("core_request_sha256", "b" * 64),
            ("core_source_event_ids", ["SYN-EVT-OTHER-001"] * 7),
            ("approval_phase", "POST_RESOLUTION"),
            ("core_status_at_issuance", "RESOLVED"),
        ):
            docs = fixtures()
            docs["twin"][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(
                    SandboxDenied, "^twin_core_prepared_snapshot_unqualified$"):
                validate_readbacks(INTENT, **docs, now=NOW)

    def test_19_core_source_snapshot_must_be_complete_and_unique(self):
        for field, value in (
            ("request_sha256", "not-a-sha256"),
            ("source_event_ids", ["SYN-EVT-DUPLICATE"] * 7),
            ("source_event_ids", ["SYN-EVT-ONE"] * 6),
            ("source_event_ids", ["SYN-EVT-ONE"] * 6 + [None]),
        ):
            docs = fixtures()
            docs["core"][field] = value
            with self.subTest(field=field, value=str(value)[:32]), self.assertRaisesRegex(
                    SandboxDenied, "^twin_core_prepared_snapshot_unqualified$"):
                validate_readbacks(INTENT, **docs, now=NOW)

    def test_20_twin_source_fingerprint_rotated_between_reads_denied(self):
        docs = fixtures()
        calls = 0
        async def get(component, path):
            nonlocal calls
            calls += 1
            result = deepcopy(docs[component])
            if calls > 3 and component == "twin":
                result["core_request_sha256"] = "b" * 64
            return result
        with self.assertRaisesRegex(
                SandboxDenied, "^twin_core_prepared_snapshot_unqualified$"):
            asyncio.run(simulate_no_effect(INTENT, get=get, now=NOW))
        self.assertEqual(calls, 6)



    def test_21_core_scope_and_nonhuman_authority_must_match(self):
        for field, value in (
            ("scenario_id", "FOREIGN-SCENARIO"),
            ("mode", "LIVE"),
            ("approval_issuer", "HUMAN_IDP"),
            ("glpi_mode", "REAL_GLPI"),
            ("human_approval_claimed", True),
        ):
            docs = fixtures()
            docs["core"][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(
                    SandboxDenied, "^core_resolution_unqualified$"):
                validate_readbacks(INTENT, **docs, now=NOW)

    def test_22_twin_signed_payload_must_precede_resolution(self):
        # These fields are emitted only after Twin verifies the stored HMAC
        # on its authenticated GET; Worker does not possess Twin signing key.
        for field, value in (
            ("scenario_id", "OTHER"),
            ("resolution_verified", True),
            ("post_resolution_readback_required", False),
        ):
            docs = fixtures()
            docs["twin"][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(
                    SandboxDenied, "^twin_simulated_approval_unqualified$"):
                validate_readbacks(INTENT, **docs, now=NOW)

    def test_23_policy_must_be_pass_and_never_claim_human(self):
        for field, value in (
            ("state", "BLOCKED"),
            ("human_approval_claimed", True),
        ):
            docs = fixtures()
            docs["policy"][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(
                    SandboxDenied, "^policy_simulation_unqualified$"):
                validate_readbacks(INTENT, **docs, now=NOW)

    def test_24_policy_flip_between_readbacks_never_emits_receipt(self):
        docs = fixtures()
        calls = 0
        async def get(component, path):
            nonlocal calls
            calls += 1
            result = deepcopy(docs[component])
            if calls > 3 and component == "policy":
                result["state"] = "BLOCKED"
            return result
        with self.assertRaisesRegex(
                SandboxDenied, "^policy_simulation_unqualified$"):
            asyncio.run(simulate_no_effect(INTENT, get=get, now=NOW))
        self.assertEqual(calls, 6)

    def test_25_source_ids_must_be_canonical_even_when_twin_agrees(self):
        for source_ids in (
            list(reversed(canonical_source_ids(INTENT["attempt_id"]))),
            canonical_source_ids("ACME-SIM-FOREIGN-001"),
            canonical_source_ids(INTENT["attempt_id"])[:6] +
                ["SYN-EVT-AAAAAAAAAAAAAAAAAAAA"],
        ):
            docs = fixtures()
            docs["core"]["source_event_ids"] = list(source_ids)
            docs["twin"]["core_source_event_ids"] = list(source_ids)
            with self.subTest(source_ids=source_ids[0]), self.assertRaisesRegex(
                    SandboxDenied, "^twin_core_prepared_snapshot_unqualified$"):
                validate_readbacks(INTENT, **docs, now=NOW)

    def test_26_receipt_digest_stable_and_bound_to_core_snapshot(self):
        docs = fixtures()
        async def get(component, path):
            return deepcopy(docs[component])
        first = asyncio.run(simulate_no_effect(INTENT, get=get, now=NOW))
        second = asyncio.run(simulate_no_effect(INTENT, get=get, now=NOW))
        self.assertEqual(first, second)
        digest = first.pop("receipt_sha256")
        expected = hashlib.sha256(json.dumps(
            first, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")).hexdigest()
        self.assertEqual(digest, expected)
        self.assertEqual(first["core_request_sha256"], docs["core"]["request_sha256"])
        self.assertEqual(first["core_source_event_ids"], canonical_source_ids(INTENT["attempt_id"]))
        self.assertEqual(first["ticket_id"], INTENT["ticket_id"])
        self.assertEqual(len(first["twin_approval_nonce_sha256"]), 64)
        self.assertNotIn("approval_nonce", first)
        self.assertFalse(first["resolution_verified"])
        self.assertEqual(first["effect_receipts"], 0)
        docs["core"]["request_sha256"] = "b" * 64
        docs["twin"]["core_request_sha256"] = "b" * 64
        rotated = asyncio.run(simulate_no_effect(INTENT, get=get, now=NOW))
        self.assertNotEqual(rotated["receipt_sha256"], digest)

    def test_27_noncanonical_attempt_denied_before_transport(self):
        bad = dict(INTENT, attempt_id="FOREIGN-ATTEMPT-001",
                   idempotency_key="FOREIGN-ATTEMPT-001")
        with self.assertRaisesRegex(SandboxDenied, "^sandbox_intent_unqualified$"):
            validate_intent(bad)
        with self.assertRaisesRegex(SandboxDenied, "^sandbox_attempt_unqualified$"):
            canonical_source_ids("FOREIGN-ATTEMPT-001")

    def test_28_temporal_readback_must_verify_receipt_digest(self):
        docs = fixtures()
        async def get(component, path):
            return deepcopy(docs[component])
        receipt = asyncio.run(simulate_no_effect(INTENT, get=get, now=NOW))
        self.assertTrue(receipt_digest_valid(receipt))
        for field, value in (
            ("effect_receipts", 1),
            ("core_request_sha256", "b" * 64),
            ("receipt_sha256", "0" * 64),
            ("core_source_event_ids", canonical_source_ids("ACME-SIM-FOREIGN-001")),
        ):
            altered = deepcopy(receipt)
            altered[field] = value
            with self.subTest(field=field):
                self.assertFalse(receipt_digest_valid(altered))
        self.assertFalse(receipt_digest_valid({"receipt_sha256": "0" * 64}))
        main = (ROOT / "app/worker/main.py").read_text()
        self.assertIn("or not receipt_digest_valid(result)", main)


    def test_29_rehashed_forged_receipt_cannot_elevate_authority(self):
        docs = fixtures()
        async def get(component, path):
            return deepcopy(docs[component])
        valid = asyncio.run(simulate_no_effect(INTENT, get=get, now=NOW))
        self.assertTrue(receipt_digest_valid(valid))
        for field, forged in (
            ("schema", "aiops.worker-live.v1"),
            ("tenant_id", "FOREIGN-TENANT"),
            ("action", "LIVE"),
            ("receipt_status", "EXECUTED"),
            ("approval_issuer", "HUMAN_IDP"),
            ("approval_kind", "HUMAN"),
            ("human_approved", True),
            ("execution_allowed", True),
            ("effect_allowed", True),
            ("live_effects_allowed", True),
            ("real_glpi_writes_allowed", True),
            ("effect_receipts", 1),
            ("effect_receipts", False),
            ("audit_transitions", ["WORKER_LIVE_EXECUTED"]),
            ("audit_authority", "CORE_TERMINAL_CONFIRMED"),
            ("receipt_phase", "POST_RESOLUTION"),
            ("core_status_at_validation", "RESOLVED"),
            ("resolution_verified", True),
            ("post_resolution_readback_required", False),
            ("core_014_015_written", True),
            ("glpi_write", True),
            ("approval_id", "HUMAN-APP-001"),
        ):
            forged_receipt = deepcopy(valid)
            forged_receipt[field] = forged
            forged_receipt["receipt_sha256"] = hashlib.sha256(json.dumps(
                {k: v for k, v in forged_receipt.items()
                 if k != "receipt_sha256"},
                sort_keys=True, separators=(",", ":"), ensure_ascii=True
            ).encode("ascii")).hexdigest()
            with self.subTest(field=field, forged=forged):
                self.assertFalse(receipt_digest_valid(forged_receipt))

    def test_30_rehashed_extra_or_missing_receipt_fields_denied(self):
        docs = fixtures()
        async def get(component, path):
            return deepcopy(docs[component])
        valid = asyncio.run(simulate_no_effect(INTENT, get=get, now=NOW))
        for change in ("extra", "missing", "raw_nonce"):
            forged = deepcopy(valid)
            if change == "extra":
                forged["execution_receipt"] = "LIVE"
            elif change == "missing":
                del forged["glpi_write"]
            else:
                forged["approval_nonce"] = "RAW-NONCE-MUST-NOT-LEAK"
            forged["receipt_sha256"] = hashlib.sha256(json.dumps(
                {k: v for k, v in forged.items() if k != "receipt_sha256"},
                sort_keys=True, separators=(",", ":"), ensure_ascii=True
            ).encode("ascii")).hexdigest()
            with self.subTest(change=change):
                self.assertFalse(receipt_digest_valid(forged))


    def test_31_temporal_receipt_binds_simulated_ticket_without_authority_escalation(self):
        docs = fixtures()
        async def get(component, path):
            return deepcopy(docs[component])
        receipt = asyncio.run(simulate_no_effect(INTENT, get=get, now=NOW))
        self.assertEqual(receipt["ticket_id"], INTENT["ticket_id"])
        self.assertTrue(receipt_digest_valid(receipt))
        # An altered receipt must not survive a digest check. A recomputed
        # checksum is not a signature or permission to create a real GLPI ticket.
        for ticket in ("GLPI-REAL-123", "SIM-GLPI-FOREIGN", "", None):
            forged = deepcopy(receipt)
            forged["ticket_id"] = ticket
            self.assertFalse(receipt_digest_valid(forged))
            forged["receipt_sha256"] = hashlib.sha256(json.dumps(
                {k: v for k, v in forged.items() if k != "receipt_sha256"},
                sort_keys=True, separators=(",", ":"), ensure_ascii=True
            ).encode("ascii")).hexdigest()
            if ticket != "SIM-GLPI-FOREIGN":
                self.assertFalse(receipt_digest_valid(forged))
            # A different well-formed synthetic ticket can be rehashed, so
            # Core MUST compare ticket_id against its persisted same-Run record.
        for component in ("core", "twin", "policy"):
            wrong = fixtures()
            wrong[component]["ticket_id"] = "SIM-GLPI-FOREIGN"
            with self.subTest(component=component), self.assertRaises(SandboxDenied):
                validate_readbacks(INTENT, **wrong, now=NOW)


    def test_32_registered_worker_service_origin_fence_before_bearer_egress(self):
        defaults = {
            "core": ("http://aiops2-core:810", 810),
            "twin": ("http://aiops2-twin:811", 811),
            "policy": ("http://aiops2-policy:813", 813),
        }
        for component, (origin, port) in defaults.items():
            self.assertEqual(validated_service_origin(component, origin), origin)
            self.assertEqual(
                validated_service_origin(component, f"http://127.0.0.1:{port}"),
                f"http://127.0.0.1:{port}")
            for unsafe in (
                "http://attacker.example:" + str(port),
                "http://169.254.169.254:" + str(port),
                "http://aiops2-core.evil:" + str(port),
                origin.replace("http:", "ftp:"),
                origin + "/api/sandbox/acme",
                origin + "?redirect=evil",
                origin + "#fragment",
                origin.replace("://", "://user:password@"),
                origin.rsplit(":", 1)[0] + ":9999",
                "http://[::1",
                "http://aiops2-core:invalid",
                "",
                None,
            ):
                with self.subTest(component=component, unsafe=unsafe):
                    with self.assertRaisesRegex(
                            SandboxDenied, "^sandbox_service_origin_unqualified$"):
                        validated_service_origin(component, unsafe)
        with self.assertRaises(SandboxDenied):
            validated_service_origin("arbitrary", "http://aiops2-core:810")
        main = (ROOT / "app/worker/main.py").read_text()
        self.assertIn("origin = validated_service_origin(", main)
        self.assertLess(main.index("origin = validated_service_origin("),
                        main.index("headers={\"Authorization\": \"Bearer \" + ADMIN"))
        # Even an allowed internal origin must not leak the service bearer
        # through HTTP_PROXY/HTTPS_PROXY/ALL_PROXY or ~/.netrc.
        activity_source = main[main.index('async def acme_simulated_no_effect('):
                               main.index('@app.get("/api/sandbox/acme/capabilities")')]
        self.assertIn("with requests.Session() as session:", activity_source)
        self.assertIn("session.trust_env = False", activity_source)
        self.assertIn("response = session.get(", activity_source)
        self.assertNotIn("response = requests.get(", activity_source)
        self.assertLess(activity_source.index("session.trust_env = False"),
                        activity_source.index("response = session.get("))



    def test_33_independent_readback_rejects_typed_snapshot_drift(self):
        # Both rounds are individually PASS/PREPARED/SIMULATED, yet the
        # authority snapshot must not move between reads. Canonical JSON
        # distinguishes 7 from 7.0 where Python dict equality does not.
        for component, field, changed in (
            ("core", "evidence_count", 3),
            ("core", "source_event_count", 7.0),
            ("twin", "impacted_cis", ["ACME-SVC-PAYMENTS", "ACME-SVC-ERP"]),
            ("policy", "risk_level", "LOW"),
        ):
            docs = fixtures()
            calls = 0

            async def get(which, path):
                nonlocal calls
                calls += 1
                result = deepcopy(docs[which])
                if calls > 3 and which == component:
                    result[field] = changed
                return result

            with self.subTest(component=component, field=field):
                # An invalid SOURCE count is now rejected by Core authority
                # validation before the cross-round snapshot comparison.
                expected = ("^core_resolution_unqualified$"
                            if component == "core" and field == "source_event_count"
                            else "^sandbox_readback_snapshot_rotated$")
                with self.assertRaisesRegex(SandboxDenied, expected):
                    asyncio.run(simulate_no_effect(INTENT, get=get, now=NOW))
                self.assertEqual(calls, 6)


    def test_34_stable_float_source_count_denied_before_temporal_receipt(self):
        # Python 7.0 == 7, but Core SOURCE count is a typed integer
        # authority claim. A stable 7.0 in both reads must not qualify.
        for malformed in (7.0, "7", True, None):
            docs = fixtures()
            docs["core"]["source_event_count"] = malformed
            calls = []

            async def get(component, path):
                calls.append(component)
                return deepcopy(docs[component])

            with self.subTest(malformed=malformed):
                with self.assertRaisesRegex(
                        SandboxDenied, "^core_resolution_unqualified$"):
                    asyncio.run(simulate_no_effect(INTENT, get=get, now=NOW))
                self.assertEqual(calls, ["core", "twin", "policy"])


if __name__ == "__main__":
    unittest.main()
