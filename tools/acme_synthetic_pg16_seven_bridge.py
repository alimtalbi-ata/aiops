"""ACME-only offline bridge for a Core-owned disposable PG16 seven-event proof.

Consumes the raw Core canonical-seven source *shape*, not a portable authority.
The Core producer owns writes, actor/tenant grants, immutable 013/014 readback,
freshness and revocation. Even a valid JSON hash triple is never authorization.
No network, database, GLPI write, LIVE action or invented runtime IDs.
"""
import argparse
import hashlib
import json
from pathlib import Path

from tools import acme_synthetic_pg16_twin_impact_handoff as twin
from tools import generate_acme_incidents as gen

SCHEMA = "aiops.acme.core-seven-pg16-proof-bridge.v1"
CORE_SCHEMA = "aiops.core-canonical-seven-source-binding.v1"
CORE_PAYLOAD_DOMAIN = "aiops.core-source-event-payload.v1"
CORE_FULL_DOMAIN = "aiops.core-full-run-event.v1"
FIXTURE = gen.ROOT / "docs/customer-story/ACME-CORE-SEVEN-PG16-PROOF-BRIDGE-UNKNOWN-2026-11-01.json"
SCOPE_KEYS = frozenset((
    "tenant_id", "incident_id", "run_id", "glpi_instance_id",
    "ticket_id", "glpi_entity_id", "permission", "actor_subject", "actor_issuer",
))
PROOF_KEYS = SCOPE_KEYS | frozenset((
    "schema", "issuer", "source_system", "observed_at", "known_at",
    "expires_at", "revoked", "events",
))
EVENT_KEYS = frozenset((
    "sequence", "source_event_id", "evidence_id", "payload",
    "payload_hash", "full_event", "full_event_hash",
))
PAYLOAD_KEYS = frozenset((
    "source_event_id", "sequence", "tenant_id", "incident_id", "run_id",
    "ticket_id", "glpi_entity_id", "ci_id", "action", "source_event_time",
    "synthetic",
))
FULL_KEYS = frozenset((
    "event_id", "run_id", "incident_id", "tenant_id", "sequence",
    "stage", "event_type", "status", "evidence_id", "source_event_id",
    "source_payload_hash", "observed_at", "known_at",
))


def _digest(domain, value):
    return hashlib.sha256(gen._canonical({"schema": domain, "event": value})).hexdigest()


def build_receipt(manifest):
    """Pinned seven-source, three-domain local matrix with zero runtime claims."""
    preview = twin.build_preview(manifest)
    events = preview["events"]
    if (len(events) != 7 or len({r["source_event_id"] for r in events}) != 7
            or [r["sequence"] for r in events] != list(range(1, 8))
            or preview["itil_stages"]["not_executed"] != 15
            or preview["checkpoints"]["not_executed"] != 6):
        raise ValueError("noncanonical ACME seven-event source")
    return {
        "schema": SCHEMA,
        "synthetic": True,
        "provenance": "SYNTHETIC_FIXTURE_ONLY",
        "seed": preview["seed"],
        "graph_version": preview["graph_version"],
        "source_replay_sha256": preview["source_replay_sha256"],
        "core_producer_schema": CORE_SCHEMA,
        "source_event_count": 7,
        "events": [{
            "sequence": e["sequence"],
            "source_event_id": e["source_event_id"],
            "ci_id": e["ci_id"],
            "acme_full_event_sha256": e["acme_full_event_sha256"],
            "acme_local_payload_sha256": e["acme_local_payload_sha256"],
            "proposed_core_payload_sha256": e["proposed_core_payload_sha256"],
            "core_pg16_full_event_sha256": None,
            "core_pg16_payload_sha256": None,
            "core_full_vs_acme_full": "UNKNOWN",
            "core_payload_vs_local_proposal": "UNKNOWN",
        } for e in events],
        "candidate_incident_count": 1,
        "candidate_incident_status": "NOT_CREATED",
        "twin_impact": preview["twin_impact"],
        "core_proof_shape": "UNAVAILABLE",
        "core_proof_reason": "NO_INDEPENDENT_CORE_PG16_READBACK",
        "compared_event_count": 0,
        "core_pg16_authority": "UNKNOWN",
        "actor_tenant_acl": "UNKNOWN",
        "immutable_audit_013_014": "UNKNOWN",
        "freshness": "UNKNOWN",
        "revocation": "UNKNOWN",
        "glpi_human_rights": "UNKNOWN",
        "hitl_approval": None,
        "runtime": {
            "tenant_id": None, "actor_subject": None,
            "incident_id": None, "run_id": None,
            "glpi_ticket_id": None, "evidence_ids": [],
        },
        "itil_stages": {"count": 15, "verified": 0, "not_executed": 15,
                        "status": "NOT_EXECUTED"},
        "checkpoints": {"count": 6, "verified": 0, "not_executed": 6,
                        "status": "NOT_EXECUTED"},
        "result": "UNKNOWN",
        "publishable_to_core_or_glpi": False,
        "live_effects_authorized": False,
    }


def _reason(proof, local, now):
    if proof is None:
        return "NO_INDEPENDENT_CORE_PG16_READBACK"
    if type(proof) is not dict or set(proof) != PROOF_KEYS:
        return "MALFORMED_OR_EXTRA_CORE_PROOF_FIELDS"
    if (proof["schema"] != CORE_SCHEMA or
            proof["source_system"] != "CORE_CANONICAL_READBACK" or
            type(proof["issuer"]) is not str or not proof["issuer"]):
        return "FOREIGN_CORE_PRODUCER"
    if any(type(proof[k]) is not str or not proof[k] for k in SCOPE_KEYS):
        return "MISSING_ACTOR_TENANT_INCIDENT_RUN_SCOPE"
    if proof["permission"] != "run:read":
        return "FOREIGN_PERMISSION"
    if proof["revoked"] is not False:
        return "REVOKED_OR_UNTRUSTED_REVOCATION"
    if (any(type(proof[k]) is not int for k in
            ("observed_at", "known_at", "expires_at")) or
            not now - 300 <= proof["observed_at"] <= proof["known_at"] <= now or
            not now < proof["expires_at"] <= now + 300):
        return "STALE_EXPIRED_OR_FUTURE_CORE_PROOF"
    rows = proof["events"]
    if type(rows) is not list or len(rows) != 7:
        return "MISSING_OR_EXTRA_CORE_EVENTS"
    if any(type(row) is not dict or set(row) != EVENT_KEYS for row in rows):
        return "MALFORMED_CORE_EVENT"
    if ([row["source_event_id"] for row in rows] !=
            [row["source_event_id"] for row in local] or
            [row["sequence"] for row in rows] != list(range(1, 8))):
        return "FOREIGN_DUPLICATE_OR_REORDERED_SOURCE_IDS"
    seen_evidence = set()
    last_known = 0
    for source, row in zip(local, rows):
        payload, full = row["payload"], row["full_event"]
        evidence_id = row["evidence_id"]
        if (type(evidence_id) is not str or not evidence_id or
                evidence_id in seen_evidence or
                type(payload) is not dict or set(payload) != PAYLOAD_KEYS or
                type(full) is not dict or set(full) != FULL_KEYS):
            return "MISSING_EVIDENCE_OR_PAYLOAD_FIELDS"
        seen_evidence.add(evidence_id)
        if (payload["synthetic"] is not True or
                payload["source_event_id"] != source["source_event_id"] or
                payload["sequence"] != source["sequence"] or
                payload["ci_id"] != source["ci_id"] or
                payload["action"] != source["action"] or
                payload["source_event_time"] != source["event_time"]):
            return "FOREIGN_TWIN_SOURCE_PAYLOAD"
        if any(payload[k] != proof[k] for k in
               ("tenant_id", "incident_id", "run_id", "ticket_id", "glpi_entity_id")):
            return "CROSS_SCOPE_CORE_PAYLOAD"
        if (full["sequence"] != source["sequence"] or
                full["source_event_id"] != source["source_event_id"] or
                full["evidence_id"] != evidence_id or
                full["run_id"] != proof["run_id"] or
                full["incident_id"] != proof["incident_id"] or
                full["tenant_id"] != proof["tenant_id"] or
                full["stage"] != "SOURCE" or full["event_type"] != "OBSERVED" or
                full["status"] != "PASS" or
                full["source_payload_hash"] != row["payload_hash"]):
            return "CROSS_SCOPE_OR_FOREIGN_CORE_FULL_EVENT"
        observed, known = full["observed_at"], full["known_at"]
        if (type(observed) is not int or type(known) is not int or
                not now - 300 <= observed <= known <= now or
                known < last_known):
            return "STALE_OR_REORDERED_EVENT_CLOCK"
        last_known = known
        if (type(row["payload_hash"]) is not str or
                type(row["full_event_hash"]) is not str or
                row["payload_hash"] != _digest(CORE_PAYLOAD_DOMAIN, payload) or
                row["full_event_hash"] != _digest(CORE_FULL_DOMAIN, full) or
                row["payload_hash"] == row["full_event_hash"]):
            return "CORE_FULL_PAYLOAD_HASH_DOMAIN_MISMATCH"
    # Structural integrity only: no TLS peer, PG16 transaction, 013/014
    # immutable audit or independently authorized actor/tenant readback here.
    return "SHAPE_CONSISTENT_BUT_NONPORTABLE_AUTHORITY"


def consume(manifest, *, core_proof=None, now=None):
    """Compare Core-owned proof claims; NEVER copy identifiers or mark VERIFIED."""
    if now is None:
        from datetime import datetime, timezone
        now = int(datetime.now(timezone.utc).timestamp())
    if type(now) is not int or now <= 0:
        raise ValueError("invalid independent clock")
    result = build_receipt(manifest)
    local = twin.build_preview(manifest)["events"]
    reason = _reason(core_proof, local, now)
    result["core_proof_reason"] = reason
    if core_proof is not None:
        result["core_proof_shape"] = (
            "CONSISTENT_UNTRUSTED" if reason ==
            "SHAPE_CONSISTENT_BUT_NONPORTABLE_AUTHORITY" else "REJECTED")
    if reason == "SHAPE_CONSISTENT_BUT_NONPORTABLE_AUTHORITY":
        result["compared_event_count"] = 7
        for output, claimed in zip(result["events"], core_proof["events"]):
            output["core_full_vs_acme_full"] = (
                "SAME_BYTES_NOT_AUTHORITY"
                if claimed["full_event_hash"] == output["acme_full_event_sha256"]
                else "DISTINCT_DOMAIN_NOT_EQUIVALENCE")
            output["core_payload_vs_local_proposal"] = (
                "SAME_BYTES_NOT_AUTHORITY"
                if claimed["payload_hash"] == output["proposed_core_payload_sha256"]
                else "SCOPE_OR_BYTES_DIFFER_NOT_AUTHORITY")
    return result


def _read_untrusted(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError("oversized untrusted Core proof")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=gen._unique_object)


def main():
    parser = argparse.ArgumentParser(description="Offline ACME Core PG16 seven bridge")
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--core-proof", type=Path)
    args = parser.parse_args()
    if args.emit and (args.check or args.core_proof):
        parser.error("--emit cannot consume Core proof or check")
    manifest = gen.replay(seed=20261018)
    if args.check and gen._canonical(_read_untrusted(FIXTURE)) != gen._canonical(build_receipt(manifest)):
        raise ValueError("modified canonical ACME Core bridge fixture")
    result = consume(manifest, core_proof=_read_untrusted(args.core_proof)
                     if args.core_proof else None)
    print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
