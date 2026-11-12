"""Offline ACME/Core SHA-domain comparison; synthetic vectors are never PG16 receipts.

Core owns the full/payload serialization and 013/014 audit. This consumer
cannot authenticate transport, actor, tenant, GLPI rights, HITL or Evidence.
"""
import argparse
import copy
import json
from pathlib import Path
import re

from tools import acme_synthetic_itil_stage_authority_consumer as itil
from tools import generate_acme_incidents as gen

SCHEMA = "aiops.acme.core-pg16-hash-comparison-negative.v1"
VECTOR_SCHEMA = "aiops.acme.independent-test-core-hash-vector.v1"
CORE_RECEIPT_SCHEMA = "aiops.core-canonical-seven-source-receipt.v1"
CORE_DOMAINS = {"payload": "aiops.core-source-event-payload.v1",
                "full_event": "aiops.core-full-run-event.v1"}
HEX64 = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
ROOT = gen.ROOT / "docs/customer-story"
VECTOR_PATH = ROOT / "ACME-INDEPENDENT-CORE-HASH-TEST-VECTOR-2026-11-01.json"
RECEIPT_PATH = ROOT / "ACME-CORE-PG16-HASH-COMPARISON-UNKNOWN-2026-11-01.json"
VECTOR_KEYS = frozenset(("schema", "provenance", "core_receipt_schema",
                         "hash_domains", "actor_subject", "tenant_id",
                         "incident_id", "run_id", "glpi_ticket_id",
                         "evidence_ids", "hitl_approval", "events"))
EVENT_KEYS = frozenset(("sequence", "source_event_id", "payload_sha256",
                        "full_event_sha256"))


def _read_json(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError("oversized untrusted fixture")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=gen._unique_object)


def _reason(source, vector):
    if vector is None:
        return "NO_INDEPENDENT_TEST_VECTOR"
    if type(vector) is not dict or set(vector) != VECTOR_KEYS:
        return "MALFORMED_OR_EXTRA_FIELDS"
    if (vector["schema"] != VECTOR_SCHEMA or
            vector["provenance"] != "TEST_ONLY_UNTRUSTED_NOT_PG16" or
            vector["core_receipt_schema"] != CORE_RECEIPT_SCHEMA or
            type(vector["hash_domains"]) is not dict or
            vector["hash_domains"] != CORE_DOMAINS):
        return "FOREIGN_OR_UNTRUSTED_HASH_DOMAIN"
    if (any(vector[k] is not None for k in
            ("actor_subject", "tenant_id", "incident_id", "run_id",
             "glpi_ticket_id", "hitl_approval")) or
            vector["evidence_ids"] != []):
        return "UNTRUSTED_RUNTIME_AUTHORITY_CLAIM"
    events = vector["events"]
    if type(events) is not list or len(events) != 7:
        return "MISSING_OR_EXTRA_EVENTS"
    expected_ids = [row["source_event_id"] for row in source["source_events"]]
    if (any(type(row) is not dict or set(row) != EVENT_KEYS for row in events) or
            [row["source_event_id"] for row in events] != expected_ids or
            [row["sequence"] for row in events] != list(range(1, 8))):
        return "FOREIGN_DUPLICATE_OR_REORDERED_EVENTS"
    digests = []
    for row in events:
        if any(type(row[k]) is not str or HEX64.fullmatch(row[k]) is None
               for k in ("payload_sha256", "full_event_sha256")):
            return "INVALID_TEST_ONLY_HASH"
        if row["payload_sha256"] == row["full_event_sha256"]:
            return "COLLAPSED_CORE_HASH_DOMAINS"
        digests.extend((row["payload_sha256"], row["full_event_sha256"]))
    if len(set(digests)) != 14:
        return "DUPLICATE_CORE_TEST_HASH"
    return "TEST_VECTOR_SHAPE_ONLY_NOT_PG16"


def compare(manifest, vector=None):
    """Compare test-only bytes; even exact equality never promotes authority."""
    source = itil.build_receipt(manifest)  # seven IDs, 15 stages, six checkpoints
    reason = _reason(source, vector)
    valid = reason == "TEST_VECTOR_SHAPE_ONLY_NOT_PG16"
    rows = []
    for i, local in enumerate(source["source_events"]):
        supplied = vector["events"][i] if valid else None
        full = supplied["full_event_sha256"] if supplied else None
        payload = supplied["payload_sha256"] if supplied else None
        rows.append({
            "sequence": local["sequence"],
            "source_event_id": local["source_event_id"],
            "acme_full_event_sha256": local["acme_full_event_sha256"],
            "acme_local_payload_sha256": local["acme_local_payload_sha256"],
            "acme_proposed_core_payload_sha256": local["proposed_core_payload_sha256"],
            "test_only_core_full_event_sha256": full,
            "test_only_core_payload_sha256": payload,
            "test_only_full_byte_comparison": (
                "MISMATCH_TEST_ONLY" if full != local["acme_full_event_sha256"]
                else "SAME_BYTES_NOT_AUTHORITY") if valid else "UNKNOWN",
            "test_only_payload_byte_comparison": (
                "MISMATCH_TEST_ONLY" if payload != local["acme_local_payload_sha256"]
                else "SAME_BYTES_NOT_AUTHORITY") if valid else "UNKNOWN",
            "core_pg16_full_event_sha256": None,
            "core_pg16_payload_sha256": None,
            "core_pg16_domain_equivalence": "UNKNOWN",
            "runtime_authority": "UNKNOWN",
        })
    return {
        "schema": SCHEMA,
        "provenance": "SYNTHETIC_FIXTURE_ONLY",
        "seed": source["seed"],
        "graph_version": source["graph_version"],
        "source_replay_sha256": source["source_replay_sha256"],
        "core_receipt_schema": CORE_RECEIPT_SCHEMA,
        "core_hash_domains": copy.deepcopy(CORE_DOMAINS),
        "test_vector_provenance": (
            "TEST_ONLY_UNTRUSTED_NOT_PG16" if valid else "UNAVAILABLE"),
        "test_vector_reason": reason,
        "source_event_count": 7,
        "comparison_rows": rows,
        "core_pg16_readback": "UNAVAILABLE",
        "core_pg16_hash_equivalence": "UNKNOWN",
        "authority": copy.deepcopy(source["authority"]),
        "stage_count": 15,
        "verified_stage_count": 0,
        "not_executed_stage_count": 15,
        "stages": copy.deepcopy(source["stages"]),
        "checkpoint_count": 6,
        "verified_checkpoint_count": 0,
        "not_executed_checkpoint_count": 6,
        "checkpoints": copy.deepcopy(source["checkpoints"]),
        "result": "UNKNOWN",
        "publishable_to_core_or_glpi": False,
        "live_effects_authorized": False,
    }


def main():
    parser = argparse.ArgumentParser(description="Offline ACME/Core hash comparison")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--emit", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--test-vector", type=Path, default=VECTOR_PATH)
    args = parser.parse_args()
    manifest = gen.replay(seed=20261018)
    vector = _read_json(args.test_vector)
    receipt = compare(manifest, vector)
    if args.check:
        pinned = _read_json(RECEIPT_PATH)
        if gen._canonical(pinned) != gen._canonical(receipt):
            raise ValueError("redacted comparison fixture drift")
        print(json.dumps({"result": "UNKNOWN", "check": "PASS_SYNTHETIC_ONLY",
                          "source_event_count": 7, "not_executed_stage_count": 15,
                          "not_executed_checkpoint_count": 6}, sort_keys=True))
    else:
        print(json.dumps(receipt, sort_keys=True, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
