"""Deterministic ACME ITIL storyboard verifier, exclusively OFFLINE/SYNTHETIC.

Validates seven pinned source events, local delivery freshness, correlation and
15 planned ITIL anchors. Never queries or writes Core/GLPI/Evidence, invokes
models, approves HITL, or claims a runtime receipt or authenticated tenant.
"""
import copy
import hashlib
import json

from tools import acme_synthetic_ingest_contract as ingest
from tools import generate_acme_incidents as gen

CANONICAL_REPLAY_FILE_SHA256 = (
    "bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8"
)


def verify_itil_replay_offline(manifest, *, test_partition="SYNTHETIC_TEST_PARTITION_A",
                               deliveries=None, candidate=None):
    """Rebuild and verify an unexecuted 15-stage replay from pinned inputs.

    `candidate`, if provided, is a proposed offline projection to validate
    against an independently recomputed result. Rehashing forged content does
    not make it trustworthy. Synthetic partitions are not tenant identities.
    """
    preflight = ingest.ingestion_preflight_offline(
        manifest, test_partition=test_partition, deliveries=deliveries)
    vertical = gen.vertical_contract_offline(manifest)
    impact = gen.event_impact_contract_offline(manifest)
    replay_file = (json.dumps(manifest, sort_keys=True, indent=2,
                              ensure_ascii=True) + "\n").encode("utf-8")
    if hashlib.sha256(replay_file).hexdigest() != CANONICAL_REPLAY_FILE_SHA256:
        raise ValueError("noncanonical ACME replay bytes")
    if (preflight["source_manifest_sha256"] != vertical["source_manifest_sha256"] or
            preflight["source_dataset_sha256"] != impact["source_dataset_sha256"] or
            preflight["graph_version"] != impact["graph_version"] or
            preflight["source_event_count"] != 7 or
            len(vertical["stages"]) != 15 or len(vertical["checkpoints"]) != 6 or
            len(preflight["local_delivery_checks"]) != 7 or
            preflight["candidate_incident"]["status"] != "NOT_CREATED"):
        raise ValueError("inconsistent synthetic source projections")

    by_id = {row["source_event_id"]: row for row in preflight["local_delivery_checks"]}
    if len(by_id) != 7:
        raise ValueError("ambiguous local delivery identity")
    stages = []
    for stage in vertical["stages"]:
        step = stage["source_step"]
        if type(step) is not int or not 1 <= step <= 7:
            raise ValueError("untrusted synthetic stage step")
        event = manifest["events"][step - 1]
        check = by_id.get(event["source_event_id"])
        if (check is None or stage["source_event_id"] != event["source_event_id"] or
                stage["source_event_time"] != event["event_time"] or
                stage["source_event_ci_id"] != event["ci_id"] or
                stage["source_action"] != event["action"] or
                stage["status"] != "NOT_EXECUTED" or
                stage["runtime_id"] is not None or stage["runtime_evidence_ids"] != [] or
                stage["anchor_is_runtime_proof"] is not False or
                check["dedupe_key"] != event["dedupe_key"] or
                check["ci_id"] != event["ci_id"] or
                check["correlation_key"] != impact["correlation"]["key"] or
                check["content_digest_sha256"] !=
                hashlib.sha256(gen._canonical(event)).hexdigest()):
            raise ValueError("ITIL anchor is not backed by pinned source event")
        stages.append({
            "stage": stage["stage"],
            "itil_practice": stage["itil_practice"],
            "status": "NOT_EXECUTED",
            "source_anchor_validation": "MATCHED_PINNED_SYNTHETIC_EVENT",
            "source_step": step,
            "source_event_id": event["source_event_id"],
            "source_event_time": event["event_time"],
            "source_known_at": event["known_at"],
            "source_ci_id": event["ci_id"],
            "source_action": event["action"],
            "source_dedupe_key": event["dedupe_key"],
            "source_event_content_sha256": check["content_digest_sha256"],
            "synthetic_first_received_at": check["synthetic_first_received_at"],
            "runtime_checkpoint": stage["runtime_checkpoint"],
            "runtime_id": None,
            "runtime_evidence_ids": [],
            "source_anchor_is_runtime_proof": False,
        })
    checkpoints = copy.deepcopy(vertical["checkpoints"])
    if any(row != {"stage": row["stage"], "status": "NOT_EXECUTED", "id": None}
           for row in checkpoints):
        raise ValueError("untrusted runtime checkpoint projection")

    result = {
        "schema": "aiops.acme.synthetic-itil-replay-verification.v1",
        "synthetic": True,
        "authority": "OFFLINE_FIXTURE_ONLY",
        "provenance": "SYNTHETIC_FIXTURE",
        "test_partition": preflight["test_partition"],
        "test_partition_is_tenant_authority": False,
        "tenant_scope": "UNKNOWN",
        "tenant_id": None,
        "seed": manifest["seed"],
        "scenario_id": manifest["scenario_id"],
        "graph_version": gen.SEED_GIT_BLOB,
        "vertical_contract_git_blob": gen.VERTICAL_CONTRACT_GIT_BLOB,
        "event_impact_contract_git_blob": gen.EVENT_IMPACT_CONTRACT_GIT_BLOB,
        "governance_index_git_blob": gen.GOVERNANCE_SOURCE_GIT_BLOB,
        "source_dataset_sha256": manifest["dataset_sha256"],
        "source_manifest_sha256": preflight["source_manifest_sha256"],
        "canonical_replay_file_sha256": CANONICAL_REPLAY_FILE_SHA256,
        "source_event_count": 7,
        "source_event_ids": copy.deepcopy(impact["source_event_ids"]),
        "delivery_count": preflight["delivery_count"],
        "duplicate_delivery_count": preflight["duplicate_delivery_count"],
        "correlation": copy.deepcopy(impact["correlation"]),
        "candidate_incident": copy.deepcopy(preflight["candidate_incident"]),
        "blast_radius_candidate": copy.deepcopy(impact["blast_radius_candidate"]),
        "itil": copy.deepcopy(impact["itil"]),
        "service_id": impact["service_id"],
        "ci_id": impact["ci_id"],
        "governance_unknowns": copy.deepcopy(vertical["governance_unknowns"]),
        "stages": stages,
        "checkpoints": checkpoints,
        "runtime_receipts": {
            "glpi_ticket_id": None,
            "core_incident_id": None,
            "core_run_id": None,
            "evidence_ids": [],
            "analyst_output": None,
            "critic_output": None,
            "policy_decision": None,
            "hitl_approval": None,
            "simulate_effect": None,
            "post_action_verification": None,
            "resolution": None,
            "reopen": None,
        },
        "runtime_readback": "NOT_EXECUTED",
        "observed_impact": "UNKNOWN",
        "priority_confirmed": "UNKNOWN",
        "source_content_hash_is_evidence_receipt": False,
        "source_anchor_is_runtime_proof": False,
        "publishable_to_core_or_glpi": False,
        "live_effects_authorized": False,
    }
    if candidate is not None:
        if type(candidate) is not dict or gen._canonical(candidate) != gen._canonical(result):
            raise ValueError("untrusted synthetic ITIL replay projection")
    return result
