"""ACME seven-event, three-SHA-domain receipt: offline fixture, never Core proof.

Core's independently scoped aiops.core-canonical-seven-source-binding.v1
requires actual Core payload and full-run-event rows. This deterministic
ACME projection cannot produce either Core receipt, actor/tenant authorization,
GLPI rights, HITL decision, or an observed impact. No HTTP or writes.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from tools import acme_synthetic_core_canonical_cross_domain as cross
from tools import generate_acme_incidents as gen

SCHEMA = "aiops.acme.synthetic-seven-event-three-domain-receipt.v1"
CORE_MANIFEST_SCHEMA = "aiops.core-canonical-seven-source-binding.v1"
CORE_FULL_SCHEMA = "aiops.core-full-run-event.v1"
RECEIPT_FILE = (gen.ROOT / "docs/customer-story" /
                "ACME-SYNTHETIC-SEVEN-EVENT-THREE-DOMAIN-RECEIPT-2026-11-01.json")
PINNED_RECEIPT_SHA256 = (
    "ed53b7b254b80e01b6ee87ad6b2949dfb3f93bb8e4904f48e0b90e75cb8ad4e7"
)


def build_receipt(manifest):
    """Project exactly seven immutable local hashes; Core authority stays absent."""
    baseline = cross.verify_core_canonical_cross_domain_offline(manifest)
    rows = baseline["source_event_hash_domains"]
    if (len(rows) != 7 or len({r["source_event_id"] for r in rows}) != 7
            or len(baseline["stages"]) != 15
            or len(baseline["checkpoints"]) != 6):
        raise ValueError("unpinned seven-event source or ITIL projection")
    projected = []
    for sequence, row in enumerate(rows, 1):
        if row["sequence"] != sequence:
            raise ValueError("noncanonical source sequence")
        digests = (row["acme_full_event_sha256"],
                   row["acme_payload_sha256_candidate"],
                   row["proposed_core_wrapped_event_sha256"])
        if len(set(digests)) != 3 or any(
                type(h) is not str or len(h) != 64
                or any(c not in "0123456789abcdef" for c in h)
                for h in digests):
            raise ValueError("conflated or invalid SHA256 domains")
        projected.append({
            "sequence": sequence,
            "source_event_id": row["source_event_id"],
            "acme_full_event_sha256": digests[0],
            "acme_local_payload_sha256": digests[1],
            "proposed_core_payload_sha256": digests[2],
            "core_full_run_event_sha256": None,
            "core_event_id": None,
            "core_evidence_id": None,
            "mapping_status": "UNVERIFIED_CROSS_DOMAIN",
        })
    return {
        "schema": SCHEMA,
        "authority": "OFFLINE_FIXTURE_ONLY",
        "provenance": "SYNTHETIC_FIXTURE",
        "synthetic": True,
        "core_manifest_schema": CORE_MANIFEST_SCHEMA,
        "core_payload_schema": cross.CORE_PAYLOAD_SCHEMA,
        "core_full_event_schema": CORE_FULL_SCHEMA,
        "core_manifest_status": "UNAVAILABLE",
        "hash_domains": {
            "acme_full_event": "SHA256_CANONICAL_ACME_FULL_EVENT",
            "acme_local_payload": "SHA256_CANONICAL_ACME_PAYLOAD",
            "proposed_core_payload":
                "SHA256_CANONICAL_SCHEMA_WRAPPED_ACME_PROJECTION_NOT_CORE",
        },
        "core_v2_mapping": {
            "events[].source_event_id": "ACME.source_event_id",
            "events[].sequence": "ONE_BASED_REPLAY_ORDER",
            "events[].payload_hash": "PROPOSED_ONLY_NOT_CORE_PAYLOAD",
            "events[].full_event_hash": "UNAVAILABLE",
            "events[].evidence_id": "UNKNOWN",
            "tenant_id": "UNKNOWN", "actor_subject": "UNKNOWN",
            "incident_id": "UNKNOWN", "run_id": "UNKNOWN",
        },
        "hash_domains_equivalent": False,
        "core_runtime_source_hashes_verified": False,
        "source_replay_sha256": baseline["canonical_replay_file_sha256"],
        "source_manifest_sha256": baseline["source_manifest_sha256"],
        "source_dataset_sha256": manifest["dataset_sha256"],
        "seed": manifest["seed"],
        "graph_version": manifest["graph_version"],
        "source_event_count": 7,
        "source_event_rows": projected,
        "runtime_authority": {
            "tenant_id": None, "actor_subject": None,
            "incident_id": None, "run_id": None,
            "glpi_ticket_id": None, "evidence_ids": [],
            "hitl_approval": None, "source": "UNAVAILABLE",
            "actor": "UNAVAILABLE", "tenant": "UNAVAILABLE",
            "impact_observed": "UNKNOWN", "priority_confirmed": "UNKNOWN",
        },
        "itil_stages": [
            {"stage": s["stage"], "status": "NOT_EXECUTED"}
            for s in baseline["stages"]
        ],
        "checkpoints": [
            {"stage": c["stage"], "status": "NOT_EXECUTED", "id": None}
            for c in baseline["checkpoints"]
        ],
        "runtime_readback": "NOT_EXECUTED",
        "publishable_to_core_or_glpi": False,
        "live_effects_authorized": False,
    }


def read_pinned_receipt(path=RECEIPT_FILE):
    """Pin the machine-readable fixture independently of the replay seed."""
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PINNED_RECEIPT_SHA256:
        raise ValueError("three-domain receipt fixture SHA256 mismatch")
    try:
        return json.loads(raw, object_pairs_hook=gen._unique_object)
    except (UnicodeError, ValueError) as exc:
        raise ValueError("invalid three-domain receipt JSON") from exc


def verify_receipt(manifest, *, receipt=None, proposal=None, now=None):
    """Check local hashes and optional adversarial proposal; never verify Core.

    `proposal` is the existing explicitly TEST_ONLY cross-domain shape. Its
    tenant/actor/freshness/revocation checks are NOT an identity attestation.
    """
    expected = build_receipt(manifest)
    if receipt is None:
        receipt = read_pinned_receipt()
    if type(receipt) is not dict or gen._canonical(receipt) != gen._canonical(expected):
        raise ValueError("foreign, reordered or forged three-domain receipt")
    checked = cross.verify_core_canonical_cross_domain_offline(
        manifest, proposal=proposal, now=now)
    if checked["result"] != "UNAVAILABLE" or checked["seven_event_readback_authenticated"]:
        raise ValueError("unexpected Core authority promotion")
    return {
        "schema": SCHEMA,
        "result": "UNAVAILABLE",
        "reason": "NO_INDEPENDENT_CORE_PG16_ACTOR_TENANT_SEVEN_EVENT_READBACK",
        "receipt_sha256": hashlib.sha256(
            (json.dumps(receipt, sort_keys=True, indent=2,
                        ensure_ascii=True) + "\n").encode("utf-8")).hexdigest(),
        "source_event_count": 7,
        "source_event_ids": [r["source_event_id"] for r in expected["source_event_rows"]],
        "three_domains_checked": True,
        "core_manifest_schema": CORE_MANIFEST_SCHEMA,
        "core_v2_full_event_hash_available": False,
        "actor_authenticated": False,
        "tenant_acl_qualified": False,
        "incident_id": None, "run_id": None,
        "glpi_ticket_id": None, "evidence_ids": [],
        "hitl_approval": None,
        "runtime_readback": "NOT_EXECUTED",
        "itil_stages": copy.deepcopy(expected["itil_stages"]),
        "checkpoints": copy.deepcopy(expected["checkpoints"]),
        "observed_impact": "UNKNOWN",
        "priority_confirmed": "UNKNOWN",
        "publishable_to_core_or_glpi": False,
        "live_effects_authorized": False,
    }


def main():
    parser = argparse.ArgumentParser(description="Offline ACME three-domain receipt")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--emit", action="store_true", help="print canonical receipt JSON")
    group.add_argument("--check", action="store_true", help="validate pinned JSON (default)")
    args = parser.parse_args()
    manifest = gen.replay(seed=20261018)
    if args.emit:
        print(json.dumps(build_receipt(manifest), sort_keys=True,
                         indent=2, ensure_ascii=True))
    else:
        print(json.dumps(verify_receipt(manifest), sort_keys=True))


if __name__ == "__main__":
    main()
