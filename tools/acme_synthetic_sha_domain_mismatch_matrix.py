"""Deterministic ACME/Core #291 SHA-domain mismatch matrix; offline only.

Seven canonical ACME events have three independent LOCAL digests. Core's
payload/full-run-event hashes and TLS/PG16 source receipt are NOT present.
This is not a Core adapter, receipt store, actor authorization or live probe.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from tools import acme_synthetic_core_canonical_cross_domain as cross
from tools import acme_synthetic_three_domain_receipt as three
from tools import generate_acme_incidents as gen

SCHEMA = "aiops.acme.synthetic-seven-sha-domain-mismatch-matrix.v1"
CORE_SOURCE_SCHEMA = "aiops.core-canonical-seven-source-binding.v1"
CORE_RECEIPT_SCHEMA = "aiops.core-canonical-seven-source-receipt.v1"
CORE_PAYLOAD_DOMAIN = "aiops.core-source-event-payload.v1"
CORE_FULL_DOMAIN = "aiops.core-full-run-event.v1"
CORE_PROOF_DOMAIN = "aiops.core-canonical-seven-transport-proof.v1"
CORE_RECEIPT_HASH_DOMAIN = "aiops.core-canonical-seven-receipt-hash.v1"
MATRIX_FILE = (gen.ROOT / "docs/customer-story" /
               "ACME-SYNTHETIC-SEVEN-SHA-DOMAIN-MISMATCH-MATRIX-2026-11-01.json")

ABSENT_RUNTIME_FIELDS = (
    "tenant_id", "actor_subject", "actor_issuer", "incident_id", "run_id",
    "glpi_ticket_id", "glpi_entity_id", "glpi_instance_id", "hitl_approval",
    "observed_at", "known_at", "revoked",
)
NEGATIVE_GATES = {
    "actor_authentication": "UNKNOWN",
    "tenant_authorization": "UNKNOWN",
    "core_incident_binding": "UNKNOWN",
    "core_run_binding": "UNKNOWN",
    "glpi_ticket_authorization": "UNKNOWN",
    "core_evidence_binding": "UNKNOWN",
    "tls_readback": "UNAVAILABLE",
    "freshness": "UNKNOWN",
    "revocation": "UNKNOWN",
    "hitl_decision": "UNKNOWN",
}


def build_matrix(manifest):
    """Validate pinned fixture and compute three LOCAL SHA256 domains.

    No Core runtime hash or Core evidence ID can be computed from ACME alone.
    The proposed Core payload uses null runtime fields, unlike actual PG16.
    """
    receipt = three.build_receipt(manifest)
    pinned = three.read_pinned_receipt()
    if gen._canonical(receipt) != gen._canonical(pinned):
        raise ValueError("unpinned source three-domain receipt")
    proposed = cross.proposed_cross_domain_rows(manifest)
    rows = receipt["source_event_rows"]
    if len(rows) != 7 or len(proposed) != 7 or len(manifest["events"]) != 7:
        raise ValueError("expected exactly seven canonical events")
    matrix = []
    for seq, (event, row, candidate) in enumerate(
            zip(manifest["events"], rows, proposed), 1):
        if (row["sequence"] != seq or candidate["sequence"] != seq or
                row["source_event_id"] != event["source_event_id"] or
                candidate["source_event_id"] != event["source_event_id"] or
                row["acme_full_event_sha256"] !=
                hashlib.sha256(gen._canonical(event)).hexdigest() or
                row["acme_local_payload_sha256"] !=
                hashlib.sha256(gen._canonical(event["payload"])).hexdigest() or
                row["proposed_core_payload_sha256"] !=
                candidate["proposed_core_wrapped_event_sha256"]):
            raise ValueError("local SHA256 domain or source event mismatch")
        hashes = (
            row["acme_full_event_sha256"],
            row["acme_local_payload_sha256"],
            row["proposed_core_payload_sha256"],
        )
        if len(set(hashes)) != 3:
            raise ValueError("conflated local hash domains")
        matrix.append({
            "sequence": seq,
            "source_event_id": event["source_event_id"],
            "acme_full_event_sha256": hashes[0],
            "acme_local_payload_sha256": hashes[1],
            "acme_proposed_core_payload_sha256": hashes[2],
            "core_runtime_payload_sha256": None,
            "core_runtime_full_event_sha256": None,
            "core_evidence_id": None,
            "domain_comparison": "THREE_LOCAL_HASHES_DISTINCT_CORE_UNAVAILABLE",
            "core_equivalence": "NOT_VERIFIED",
        })
    if len({row["source_event_id"] for row in matrix}) != 7:
        raise ValueError("duplicate canonical source event ID")
    if (len(receipt["itil_stages"]) != 15 or
            len(receipt["checkpoints"]) != 6 or
            any(x["status"] != "NOT_EXECUTED"
                for x in receipt["itil_stages"] + receipt["checkpoints"])):
        raise ValueError("runtime ITIL state cannot be promoted")
    runtime = {key: None for key in ABSENT_RUNTIME_FIELDS}
    runtime["evidence_ids"] = []
    return {
        "schema": SCHEMA,
        "source": "PINNED_ACME_SYNTHETIC_FIXTURE_ONLY",
        "synthetic": True,
        "authority": "OFFLINE_TEST_ONLY",
        "test_partition": "SYNTHETIC_TEST_PARTITION_A",
        "test_partition_is_tenant_authority": False,
        "seed": receipt["seed"],
        "graph_version": receipt["graph_version"],
        "source_replay_sha256": receipt["source_replay_sha256"],
        "source_manifest_sha256": receipt["source_manifest_sha256"],
        "source_dataset_sha256": receipt["source_dataset_sha256"],
        "source_event_count": 7,
        "core_source_schema": CORE_SOURCE_SCHEMA,
        "core_receipt_schema": CORE_RECEIPT_SCHEMA,
        "hash_domains": {
            "acme_full_event": "SHA256_ACME_CANONICAL_FULL_EVENT",
            "acme_local_payload": "SHA256_ACME_CANONICAL_PAYLOAD",
            "acme_proposed_core_payload": CORE_PAYLOAD_DOMAIN,
            "core_runtime_payload": CORE_PAYLOAD_DOMAIN,
            "core_runtime_full_event": CORE_FULL_DOMAIN,
            "core_source_proof": CORE_PROOF_DOMAIN,
            "core_receipt": CORE_RECEIPT_HASH_DOMAIN,
        },
        "hash_domain_serialization": {
            "acme": "SHA256_SORTED_COMPACT_ASCII_JSON",
            "core": "SHA256_SORTED_COMPACT_ASCII_JSON_SCHEMA_AND_EVENT",
            "proposed_core_payload_is_not_runtime_payload": True,
        },
        "hash_matrix": matrix,
        "core_runtime_hash_equivalence": "NOT_VERIFIED",
        "negative_fixture_status": "MISSING_INDEPENDENT_RUNTIME_EVIDENCE",
        "negative_authority_gates": copy.deepcopy(NEGATIVE_GATES),
        "runtime_references": runtime,
        "core_source_receipt": None,
        "core_pg16_readback": "UNAVAILABLE",
        "runtime_readback": "NOT_EXECUTED",
        "observed_impact": "UNKNOWN",
        "priority_confirmed": "UNKNOWN",
        "itil_stages": copy.deepcopy(receipt["itil_stages"]),
        "checkpoints": copy.deepcopy(receipt["checkpoints"]),
        "result": "UNAVAILABLE",
        "publishable_to_core_or_glpi": False,
        "live_effects_authorized": False,
    }


def read_fixture(path=MATRIX_FILE):
    """Read strict JSON; never treat fixture contents as a Core response."""
    raw = Path(path).read_bytes()
    try:
        return json.loads(raw, object_pairs_hook=gen._unique_object)
    except (UnicodeError, ValueError) as exc:
        raise ValueError("invalid synthetic matrix JSON") from exc


def verify_matrix(manifest, *, fixture=None):
    """Reject tampering/authority promotion; always return UNAVAILABLE."""
    expected = build_matrix(manifest)
    candidate = read_fixture() if fixture is None else fixture
    if (type(candidate) is not dict or
            gen._canonical(candidate) != gen._canonical(expected)):
        raise ValueError("foreign, stale, forged or reordered synthetic matrix")
    return {
        "schema": SCHEMA,
        "result": "UNAVAILABLE",
        "core_pg16_readback": "UNAVAILABLE",
        "core_hash_equivalence": "NOT_VERIFIED",
        "source_event_count": 7,
        "tenant_authorized": False,
        "actor_authenticated": False,
        "incident_id": None,
        "run_id": None,
        "glpi_ticket_id": None,
        "evidence_ids": [],
        "hitl_approval": None,
        "itil_stages": copy.deepcopy(expected["itil_stages"]),
        "checkpoints": copy.deepcopy(expected["checkpoints"]),
        "runtime_readback": "NOT_EXECUTED",
        "publishable_to_core_or_glpi": False,
        "live_effects_authorized": False,
    }


def main():
    parser = argparse.ArgumentParser(description="Offline seven-event SHA mismatch")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--emit", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    manifest = gen.replay(seed=20261018)
    if args.emit:
        print(json.dumps(build_matrix(manifest), sort_keys=True,
                         indent=2, ensure_ascii=True))
    else:
        print(json.dumps(verify_matrix(manifest), sort_keys=True,
                         ensure_ascii=True))


if __name__ == "__main__":
    main()
