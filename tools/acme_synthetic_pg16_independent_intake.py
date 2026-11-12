"""Fail-closed ACME consumer for a separately supplied Core-owned PG16 readback.

The Core seven-event receipt is non-portable: JSON alone cannot authenticate
transport, actor/tenant ACL, immutable migrations 013/014, revocation or
Evidence. This module compares supplied *claims* with three pinned local
SHA256 domains but NEVER promotes an offline document to Core/GLPI/HITL
authority. Core owns the producer and an independently authenticated adapter.
No HTTP, database, secrets, effects, or new authoritative store.
"""
import argparse
import copy
import json
from pathlib import Path

from tools import acme_synthetic_core_readback_unknown_gate as core
from tools import acme_synthetic_itil_stage_authority_consumer as itil
from tools import generate_acme_incidents as gen

SCHEMA = "aiops.acme.core-pg16-independent-intake.v1"
RECEIPT_PATH = (gen.ROOT / "docs/customer-story" /
                "ACME-CORE-PG16-INDEPENDENT-INTAKE-UNKNOWN-2026-11-01.json")


def _read_untrusted(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError("oversized untrusted Core/proof document")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=gen._unique_object)


def build_receipt(manifest):
    """Pin source and ITIL counts before inspecting any caller-supplied data."""
    base = itil.build_receipt(manifest)
    events = base["source_events"]
    stages = base["stages"]
    checkpoints = base["checkpoints"]
    if (len(events) != 7 or len({r["source_event_id"] for r in events}) != 7
            or [r["sequence"] for r in events] != list(range(1, 8))
            or len(stages) != 15 or len(checkpoints) != 6
            or any(s["status"] != "NOT_EXECUTED" for s in stages)
            or any(c["status"] != "NOT_EXECUTED" or c["id"] is not None
                   for c in checkpoints)):
        raise ValueError("unpinned ACME replay or promoted ITIL authority")
    return {
        "schema": SCHEMA,
        "synthetic": True,
        "provenance": "SYNTHETIC_FIXTURE_ONLY",
        "seed": base["seed"],
        "graph_version": base["graph_version"],
        "source_replay_sha256": base["source_replay_sha256"],
        "core_receipt_schema": core.CORE_SCHEMA,
        "source_event_count": 7,
        "events": [{
            "sequence": r["sequence"],
            "source_event_id": r["source_event_id"],
            "acme_full_event_sha256": r["acme_full_event_sha256"],
            "acme_local_payload_sha256": r["acme_local_payload_sha256"],
            "proposed_core_payload_sha256": r["proposed_core_payload_sha256"],
            "supplied_core_full_event_sha256": None,
            "supplied_core_payload_sha256": None,
            "core_pg16_full_event_sha256": None,
            "core_pg16_payload_sha256": None,
            "full_byte_comparison": "UNKNOWN",
            "payload_byte_comparison": "UNKNOWN",
        } for r in events],
        "readback_status": "UNAVAILABLE",
        "readback_reason": "NO_INDEPENDENT_CORE_READBACK",
        "actor_tenant_acl": "UNKNOWN",
        "freshness": "UNKNOWN",
        "revocation": "UNKNOWN",
        "audit_013_014": "UNKNOWN",
        "audit_proofs_status": "UNAVAILABLE",
        "audit_proofs_reason": "NO_INDEPENDENT_AUDIT_013_014_OR_REVOCATION",
        "core_pg16_hash_equivalence": "UNKNOWN",
        "authority": {
            "actor_subject": None, "tenant_id": None,
            "incident_id": None, "run_id": None,
            "glpi_ticket_id": None, "evidence_ids": [],
            "hitl_approval": None,
        },
        "stage_count": 15,
        "verified_stage_count": 0,
        "not_executed_stage_count": 15,
        "stages": [{"stage": s["stage"], "status": "NOT_EXECUTED"}
                   for s in stages],
        "checkpoint_count": 6,
        "verified_checkpoint_count": 0,
        "not_executed_checkpoint_count": 6,
        "checkpoints": [{"stage": c["stage"], "status": "NOT_EXECUTED",
                         "id": None} for c in checkpoints],
        "result": "UNKNOWN",
        "publishable_to_core_or_glpi": False,
        "live_effects_authorized": False,
    }


def consume(manifest, *, core_readback=None, audit_proofs=None,
            expected_tenant=None, expected_actor_sha256=None, now=None):
    """Compare untrusted bytes without copying IDs, secrets or proof assertions.

    The caller's expected tenant/actor values are *comparison hints*, not
    independent authentication. A portable audit_proofs JSON is never an
    immutable 013/014 attestation. No positive verification path exists here.
    """
    result = build_receipt(manifest)
    shape = core.assess_readback(
        manifest, core_readback, expected_tenant=expected_tenant,
        expected_actor_sha256=expected_actor_sha256, now=now)
    result["readback_status"] = shape["core_readback"]
    result["readback_reason"] = shape["reason"]

    # Only structurally consistent Core-owned *claims* are compared. They
    # remain untrusted even when byte-for-byte equal to a local ACME domain.
    if shape["reason"] == "NO_INDEPENDENT_PG16_AUTHORITY":
        for local, claim in zip(result["events"], core_readback["events"]):
            full, payload = claim["full_event_sha256"], claim["payload_sha256"]
            local["supplied_core_full_event_sha256"] = full
            local["supplied_core_payload_sha256"] = payload
            local["full_byte_comparison"] = (
                "SAME_BYTES_NOT_AUTHORITY" if full == local["acme_full_event_sha256"]
                else "MISMATCH_UNAUTHENTICATED")
            local["payload_byte_comparison"] = (
                "SAME_BYTES_NOT_AUTHORITY"
                if payload == local["acme_local_payload_sha256"]
                else "MISMATCH_UNAUTHENTICATED")

    if audit_proofs is not None:
        if type(audit_proofs) is not dict:
            raise ValueError("invalid untrusted audit/revocation document")
        result["audit_proofs_status"] = "UNVERIFIED"
        result["audit_proofs_reason"] = "PORTABLE_PROOF_NOT_INDEPENDENT_ATTESTATION"
        # A revocation claim is a veto, never evidence of active authority.
        if audit_proofs.get("revocation") == "REVOKED":
            result["audit_proofs_reason"] = "REVOKED_CLAIM_FAIL_CLOSED"
            result["revocation"] = "UNKNOWN"
    return result


def verify_fixture(manifest, candidate):
    expected = build_receipt(manifest)
    if type(candidate) is not dict or gen._canonical(candidate) != gen._canonical(expected):
        raise ValueError("modified or promoted redacted intake fixture")
    return expected


def main():
    parser = argparse.ArgumentParser(description="Offline ACME PG16 readback intake")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--emit", action="store_true")
    group.add_argument("--check", action="store_true")
    parser.add_argument("--readback", type=Path)
    parser.add_argument("--audit-proofs", type=Path)
    args = parser.parse_args()
    manifest = gen.replay(seed=20261018)
    if args.emit:
        print(json.dumps(build_receipt(manifest), sort_keys=True,
                         indent=2, ensure_ascii=True))
        return
    if args.check:
        verify_fixture(manifest, _read_untrusted(RECEIPT_PATH))
    result = consume(
        manifest,
        core_readback=_read_untrusted(args.readback) if args.readback else None,
        audit_proofs=_read_untrusted(args.audit_proofs) if args.audit_proofs else None)
    if args.check:
        print(json.dumps({
            "check": "PASS_SYNTHETIC_ONLY",
            "result": "UNKNOWN",
            "verified_stage_count": result["verified_stage_count"],
            "verified_checkpoint_count": result["verified_checkpoint_count"],
            "source_event_count": result["source_event_count"],
        }, sort_keys=True))
    else:
        print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
