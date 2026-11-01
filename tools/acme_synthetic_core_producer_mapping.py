"""ACME seven-event producer/Core hash-domain comparison, offline only.

No API, GLPI, identity or runtime receipt. A matching synthetic proposal is
never an authenticated Core readback or actor/tenant authorization.
"""
import argparse
import copy
import hashlib
import json
from tools import generate_acme_incidents as gen
from tools import acme_synthetic_three_domain_receipt as three
from tools import acme_synthetic_core_canonical_cross_domain as cross

SCHEMA = "aiops.acme.core-seven-producer-cross-domain-fixture.v1"
CORE_SOURCE = "aiops.core-canonical-seven-source-binding.v1"
CORE_RECEIPT = "aiops.core-canonical-seven-source-receipt.v1"
PAYLOAD = "aiops.core-source-event-payload.v1"
FULL = "aiops.core-full-run-event.v1"
PROOF = "aiops.core-canonical-seven-transport-proof.v1"
RECEIPT_HASH = "aiops.core-canonical-seven-receipt-hash.v1"
FILE = gen.ROOT / "docs/customer-story/ACME-CORE-SEVEN-PRODUCER-CROSS-DOMAIN-FIXTURE-2026-11-01.json"
SOURCE = "ACME_OFFLINE_PRODUCER_PROPOSAL"
PARTITION = "SYNTHETIC_TEST_PARTITION_A"
TENANT = "TEST_ONLY_TENANT_A"
ACTOR = "TEST_ONLY_ACTOR_A"
PROPOSAL_KEYS = frozenset(("schema", "source", "test_partition", "tenant_id",
                           "actor_subject", "observed_at", "known_at",
                           "expires_at", "revoked", "verified",
                           "core_receipt", "source_event_rows"))


def build_fixture(manifest):
    source = three.build_receipt(manifest)
    if gen._canonical(source) != gen._canonical(three.read_pinned_receipt()):
        raise ValueError("source receipt changed")
    proposed = cross.proposed_cross_domain_rows(manifest)
    if len(proposed) != 7 or len(source["source_event_rows"]) != 7:
        raise ValueError("seven events required")
    rows = []
    for seq, (s, c) in enumerate(zip(source["source_event_rows"], proposed), 1):
        if s["sequence"] != seq or c["sequence"] != seq or s["source_event_id"] != c["source_event_id"]:
            raise ValueError("source order or ID mismatch")
        payload = c["proposed_core_event"]
        if any(payload.get(k) is not None for k in ("tenant_id", "incident_id",
               "run_id", "ticket_id", "glpi_entity_id", "metric")):
            raise ValueError("runtime scope forged")
        candidate = hashlib.sha256(gen._canonical({"schema": PAYLOAD, "event": payload})).hexdigest()
        if candidate != s["proposed_core_payload_sha256"]:
            raise ValueError("Core canonical producer hash mismatch")
        hashes = {"acme_full_event": s["acme_full_event_sha256"],
                  "acme_local_payload": s["acme_local_payload_sha256"],
                  "proposed_core_payload": candidate}
        if len(set(hashes.values())) != 3:
            raise ValueError("hash domains conflated")
        rows.append({"sequence": seq, "source_event_id": s["source_event_id"],
                     "sha256_domains": hashes, "core_persisted_payload_sha256": None,
                     "core_full_run_event_sha256": None, "core_evidence_id": None,
                     "mapping_status": "UNAVAILABLE"})
    return {
        "schema": SCHEMA, "authority": "OFFLINE_SYNTHETIC_PRODUCER_ONLY",
        "synthetic": True, "provenance": "SYNTHETIC_FIXTURE",
        "seed": source["seed"], "graph_version": source["graph_version"],
        "source_replay_sha256": source["source_replay_sha256"],
        "source_manifest_sha256": source["source_manifest_sha256"],
        "source_dataset_sha256": source["source_dataset_sha256"],
        "pinned_three_domain_receipt_sha256": three.PINNED_RECEIPT_SHA256,
        "source_event_count": 7, "source_event_rows": rows,
        "core_source_schema": CORE_SOURCE, "core_receipt_schema": CORE_RECEIPT,
        "core_payload_domain": PAYLOAD, "core_full_event_domain": FULL,
        "core_transport_proof_domain": PROOF, "core_receipt_hash_domain": RECEIPT_HASH,
        "canonicalization": "SHA256_OF_ASCII_JSON_SORTED_KEYS_COMPACT_SEPARATORS_SCHEMA_EVENT",
        "core_runtime_receipt": None, "core_runtime_status": "UNAVAILABLE",
        "core_hash_domain_equivalence": False,
        "runtime_authority": {"tenant_id": None, "actor_subject": None,
            "incident_id": None, "run_id": None, "glpi_ticket_id": None,
            "evidence_ids": [], "hitl_approval": None,
            "tenant": "UNKNOWN", "actor": "UNKNOWN", "incident": "UNKNOWN",
            "run": "UNKNOWN", "observed_impact": "UNKNOWN",
            "priority_confirmed": "UNKNOWN"},
        "itil_stages": copy.deepcopy(source["itil_stages"]),
        "checkpoints": copy.deepcopy(source["checkpoints"]),
        "runtime_readback": "NOT_EXECUTED",
        "publishable_to_core_or_glpi": False, "live_effects_authorized": False,
    }


def verify_fixture(manifest, *, fixture=None, proposal=None, now=None):
    expected = build_fixture(manifest)
    if fixture is None:
        fixture = json.loads(FILE.read_text(encoding="utf-8"),
                             object_pairs_hook=gen._unique_object)
    if type(fixture) is not dict or gen._canonical(fixture) != gen._canonical(expected):
        raise ValueError("forged producer fixture")
    if proposal is not None:
        if type(proposal) is not dict or set(proposal) != PROPOSAL_KEYS:
            raise ValueError("untrusted test proposal shape")
        if (proposal["schema"] != SCHEMA or proposal["source"] != SOURCE
                or proposal["test_partition"] != PARTITION
                or proposal["tenant_id"] != TENANT or proposal["actor_subject"] != ACTOR
                or proposal["revoked"] is not False or proposal["verified"] is not False
                or proposal["core_receipt"] is not None):
            raise ValueError("foreign or forged Core authority")
        observed, known, expiry = (proposal[k] for k in
                                   ("observed_at", "known_at", "expires_at"))
        if (type(now) is not int or
                any(type(v) is not int for v in (observed, known, expiry))
                or not now - 300 <= observed <= known <= now
                or not now < expiry <= now + 300):
            raise ValueError("stale or revoked test proposal")
        if gen._canonical(proposal["source_event_rows"]) != gen._canonical(expected["source_event_rows"]):
            raise ValueError("forged source hashes")
    return {
        "schema": SCHEMA, "result": "UNAVAILABLE",
        "reason": "NO_INDEPENDENT_CORE_PG16_ACTOR_TENANT_SEVEN_EVENT_READBACK",
        "source_event_count": 7,
        "source_event_ids": [r["source_event_id"] for r in expected["source_event_rows"]],
        "three_sha256_domains_checked": True, "core_receipt_schema": CORE_RECEIPT,
        "core_runtime_receipt": None, "actor_authenticated": False,
        "tenant_acl_qualified": False, "tenant_id": None, "actor_subject": None,
        "incident_id": None, "run_id": None, "glpi_ticket_id": None,
        "evidence_ids": [], "hitl_approval": None,
        "observed_impact": "UNKNOWN", "priority_confirmed": "UNKNOWN",
        "runtime_readback": "NOT_EXECUTED",
        "itil_stages": copy.deepcopy(expected["itil_stages"]),
        "checkpoints": copy.deepcopy(expected["checkpoints"]),
        "publishable_to_core_or_glpi": False, "live_effects_authorized": False,
    }


def main():
    parser = argparse.ArgumentParser(description="Offline ACME Core producer mapping")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--emit", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    manifest = gen.replay(seed=20261018)
    if args.emit:
        print(json.dumps(build_fixture(manifest), sort_keys=True, indent=2, ensure_ascii=True))
    else:
        print(json.dumps(verify_fixture(manifest), sort_keys=True))


if __name__ == "__main__":
    main()
