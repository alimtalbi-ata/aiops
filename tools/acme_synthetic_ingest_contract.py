"""Offline-only ACME synthetic ingestion preflight. No API, Core, GLPI or writes.

Test partitions are NOT authenticated tenant IDs; tenant authority remains UNKNOWN.
"""
from collections import Counter
import copy
from datetime import datetime
import hashlib
import re

from tools import generate_acme_incidents as gen

PARTITIONS = frozenset(("SYNTHETIC_TEST_PARTITION_A", "SYNTHETIC_TEST_PARTITION_B"))


def _projection(manifest):
    result = gen.event_impact_contract_offline(manifest)
    if (result["event_count"] != 7 or result["graph_version"] != gen.SEED_GIT_BLOB or
            result["source_dataset_sha256"] !=
            "ce0aef74222699da695c2e894e622b0625c992ef654dda34a84cff26b5e64f3f"):
        raise ValueError("unpinned ACME replay")
    return result


def synthetic_deliveries_offline(manifest, *, test_partition="SYNTHETIC_TEST_PARTITION_A"):
    if type(test_partition) is not str or test_partition not in PARTITIONS:
        raise ValueError("unknown synthetic test partition")
    _projection(manifest)
    return [
        {"test_partition": test_partition, "source_dataset_sha256": manifest["dataset_sha256"],
         "synthetic_received_at": gen._stamp(e["at_seconds"] + 2),
         "event": copy.deepcopy(e)}
        for e in manifest["events"]
    ]


def ingestion_preflight_offline(manifest, *, test_partition="SYNTHETIC_TEST_PARTITION_A",
                                deliveries=None):
    """Strict seven-event source validation, local dedup, candidate-only impact.

    Hashes are content digests, NOT immutable Evidence-service receipts.
    No runtime tenant, Incident, Run or GLPI identity is asserted.
    """
    if type(test_partition) is not str or test_partition not in PARTITIONS:
        raise ValueError("unknown synthetic test partition")
    projection = _projection(manifest)
    expected = {e["source_event_id"]: e for e in manifest["events"]}
    if len(expected) != 7 or len({e["dedupe_key"] for e in expected.values()}) != 7:
        raise ValueError("ambiguous canonical source identities")
    if deliveries is None:
        deliveries = synthetic_deliveries_offline(manifest, test_partition=test_partition)
    if type(deliveries) is not list or not 7 <= len(deliveries) <= 14:
        raise ValueError("missing or unbounded synthetic deliveries")
    counts = Counter()
    clocks = {}
    for row in deliveries:
        if type(row) is not dict or set(row) != {
                "test_partition", "source_dataset_sha256", "synthetic_received_at", "event"}:
            raise ValueError("untrusted delivery envelope")
        if (row["test_partition"] != test_partition or
                row["source_dataset_sha256"] != manifest["dataset_sha256"]):
            raise ValueError("cross-partition or foreign replay delivery")
        event = row["event"]
        if type(event) is not dict:
            raise ValueError("untrusted delivery event")
        eid = event.get("source_event_id")
        if eid not in expected or gen._canonical(event) != gen._canonical(expected[eid]):
            raise ValueError("forged source event or conflicting dedupe delivery")
        stamp = row["synthetic_received_at"]
        if type(stamp) is not str or not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", stamp):
            raise ValueError("invalid synthetic delivery clock")
        try:
            received = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            known = datetime.fromisoformat(event["known_at"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("invalid synthetic delivery clock") from exc
        if not 0 <= (received - known).total_seconds() <= 300:
            raise ValueError("stale synthetic delivery")
        counts[eid] += 1
        clocks.setdefault(eid, []).append(stamp)
    if set(counts) != set(expected):
        raise ValueError("incomplete canonical seven-event delivery set")
    checks = [
        {"source_event_id": e["source_event_id"], "dedupe_key": e["dedupe_key"],
         "correlation_key": e["correlation_key"], "ci_id": e["ci_id"],
         "content_digest_sha256": hashlib.sha256(gen._canonical(e)).hexdigest(),
         "delivery_count": counts[e["source_event_id"]],
         "synthetic_first_received_at": min(clocks[e["source_event_id"]]),
         "synthetic_last_received_at": max(clocks[e["source_event_id"]]),
         "status": "OFFLINE_VALIDATED_NOT_INGESTED"}
        for e in manifest["events"]
    ]
    return {
        "schema": "aiops.acme.synthetic-ingestion-preflight.v1",
        "authority": "OFFLINE_FIXTURE_ONLY", "provenance": "SYNTHETIC_FIXTURE",
        "synthetic": True, "test_partition": test_partition,
        "test_partition_is_tenant_authority": False,
        "tenant_scope": "UNKNOWN", "tenant_id": None,
        "source_dataset_sha256": manifest["dataset_sha256"],
        "source_manifest_sha256": hashlib.sha256(gen._canonical(manifest)).hexdigest(),
        "graph_version": gen.SEED_GIT_BLOB,
        "event_impact_contract_git_blob": gen.EVENT_IMPACT_CONTRACT_GIT_BLOB,
        "seed": manifest["seed"], "scenario_id": manifest["scenario_id"],
        "source_event_count": 7, "delivery_count": len(deliveries),
        "duplicate_delivery_count": len(deliveries) - 7,
        "local_delivery_checks": checks,
        "dedupe_scope": "TEST_PARTITION_AND_SOURCE_EVENT_ID_AND_DEDUPE_KEY",
        "correlation": copy.deepcopy(projection["correlation"]),
        "candidate_incident": {
            "status": "NOT_CREATED", "incident_id": None, "run_id": None,
            "ticket_id": None, "evidence_ids": [],
            "source_event_ids": list(projection["source_event_ids"]),
            "correlation_key": projection["correlation"]["key"],
            "service_id": projection["service_id"], "ci_id": projection["ci_id"],
            "priority_candidate": projection["itil"]["priority_candidate"],
            "priority_confirmed": "UNKNOWN", "observed_impact": "UNKNOWN"},
        "blast_radius_candidate": copy.deepcopy(projection["blast_radius_candidate"]),
        "itil_stages": [
            {"stage": s["stage"], "status": "NOT_EXECUTED",
             "source_event_id": s["source_event_id"], "runtime_id": None}
            for s in projection["stages"]],
        "checkpoints": copy.deepcopy(projection["checkpoints"]),
        "runtime_readback": "NOT_EXECUTED",
        "content_hash_is_evidence_receipt": False,
        "publishable_to_core_or_glpi": False, "live_effects_authorized": False,
    }
