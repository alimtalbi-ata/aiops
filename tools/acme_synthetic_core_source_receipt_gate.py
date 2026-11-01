"""Fail-closed ACME comparison to Core #291 informational source-receipt shape.

This is a pure offline, TEST_ONLY parser. No network, Core credentials,
PG16 reads, persisted Core/Evidence IDs, actor/tenant authorization or writes.
Even a structurally correct caller-supplied shape is never a Core receipt proof.
"""
from __future__ import annotations

import hashlib
import json
import re

from tools import acme_synthetic_three_domain_receipt as three
from tools import generate_acme_incidents as gen

SCHEMA = "aiops.acme.core-source-receipt-shape-gap.v1"
CORE_RECEIPT_SCHEMA = "aiops.core-canonical-seven-source-receipt.v1"
CORE_PROOF_DOMAIN = "aiops.core-canonical-seven-transport-proof.v1"
CORE_RECEIPT_HASH_DOMAIN = "aiops.core-canonical-seven-receipt-hash.v1"
CORE_PAYLOAD_DOMAIN = "aiops.core-source-event-payload.v1"
CORE_FULL_DOMAIN = "aiops.core-full-run-event.v1"
_HEX = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_FIELDS = frozenset((
    "schema", "decision", "link_status", "source_preflight", "transport",
    "portable_signature", "issuer", "source_system", "tenant_id",
    "incident_id", "run_id", "glpi_instance_id", "ticket_id",
    "glpi_entity_id", "permission", "actor_issuer", "actor_subject_sha256",
    "source_event_id", "source_payload_hash", "observed_at", "known_at",
    "expires_at", "event_count", "hash_domains", "events",
    "source_proof_sha256", "receipt_sha256",
))
_EVENT_FIELDS = frozenset((
    "sequence", "source_event_id", "evidence_id",
    "payload_sha256", "full_event_sha256",
))


def core_receipt_digest(value):
    """Reproduce Core's declared byte domain; NOT a signature/verifier."""
    return hashlib.sha256(json.dumps(
        {"schema": CORE_RECEIPT_HASH_DOMAIN, "event": value},
        sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("ascii")).hexdigest()


def _fail(message):
    raise ValueError("untrusted Core receipt shape: " + message)


def inspect_untrusted_receipt(manifest, *, candidate=None, now=None,
                              expected_test_tenant=None,
                              expected_test_actor_sha256=None):
    """Compare seven source IDs and three local SHA domains, fail closed.

    A candidate is caller-supplied TEST_ONLY data, not HTTPS/PG16 evidence.
    Matching IDs and valid Core-style digest bytes do NOT prove transport,
    provenance, actor, tenant, GLPI permission, or ACME/Core hash equivalence.
    """
    pinned = three.build_receipt(manifest)
    rows = pinned["source_event_rows"]
    if len(rows) != 7 or len(pinned["itil_stages"]) != 15 or len(pinned["checkpoints"]) != 6:
        _fail("unpinned ACME replay")
    result = {
        "schema": SCHEMA,
        "source": "ACME_OFFLINE_SYNTHETIC_ONLY",
        "result": "UNAVAILABLE",
        "core_receipt_schema": CORE_RECEIPT_SCHEMA,
        "core_receipt_shape": "NOT_SUPPLIED",
        "reason": "NO_INDEPENDENT_CORE_PG16_ACTOR_TENANT_READBACK",
        "source_event_ids": [r["source_event_id"] for r in rows],
        "source_event_count": 7,
        "acme_three_domains_checked": True,
        "core_payload_domain": CORE_PAYLOAD_DOMAIN,
        "core_full_event_domain": CORE_FULL_DOMAIN,
        "core_source_proof_domain": CORE_PROOF_DOMAIN,
        "core_receipt_hash_domain": CORE_RECEIPT_HASH_DOMAIN,
        "cross_domain_equivalence": "NOT_VERIFIED",
        "transport_authenticated": False,
        "actor_authenticated": False,
        "tenant_authorized": False,
        "revocation_checked": False,
        "glpi_human_permission_verified": False,
        "tenant_id": None, "actor_subject": None,
        "incident_id": None, "run_id": None, "glpi_ticket_id": None,
        "evidence_ids": [], "hitl_approval": None,
        "observed_impact": "UNKNOWN", "priority_confirmed": "UNKNOWN",
        "itil_stages": pinned["itil_stages"],
        "checkpoints": pinned["checkpoints"],
        "runtime_readback": "NOT_EXECUTED",
        "publishable_to_core_or_glpi": False,
        "live_effects_authorized": False,
    }
    if candidate is None:
        return result
    if type(now) is not int:
        _fail("explicit integer test clock required")
    if type(candidate) is not dict or set(candidate) != _FIELDS:
        _fail("missing or extra fields")
    if (candidate["schema"] != CORE_RECEIPT_SCHEMA
            or candidate["decision"] != "UNKNOWN"
            or candidate["link_status"] != "UNKNOWN"
            or candidate["source_preflight"] != "PASS_SYNTHETIC_ONLY"
            or candidate["transport"] != "TLS_AUTHENTICATED_NONPORTABLE"
            or candidate["portable_signature"] != "NONE"
            or candidate["source_system"] != "CORE_CANONICAL_READBACK"
            or candidate["permission"] != "run:read"
            or type(candidate["event_count"]) is not int
            or candidate["event_count"] != 7):
        _fail("forged authority or schema")
    for field in ("issuer", "tenant_id", "incident_id", "run_id",
                  "glpi_instance_id", "ticket_id", "glpi_entity_id",
                  "actor_issuer", "source_event_id"):
        if type(candidate[field]) is not str or not candidate[field]:
            _fail("invalid scope or provenance")
    for field in ("actor_subject_sha256", "source_payload_hash",
                  "source_proof_sha256", "receipt_sha256"):
        if type(candidate[field]) is not str or not _HEX.fullmatch(candidate[field]):
            _fail("invalid digest")
    if (expected_test_tenant is not None
            and candidate["tenant_id"] != expected_test_tenant):
        _fail("foreign TEST_ONLY tenant")
    if (expected_test_actor_sha256 is not None
            and candidate["actor_subject_sha256"] != expected_test_actor_sha256):
        _fail("foreign TEST_ONLY actor")
    if (type(candidate["hash_domains"]) is not dict
            or candidate["hash_domains"] != {
                "payload": CORE_PAYLOAD_DOMAIN,
                "full_event": CORE_FULL_DOMAIN,
                "acme_full_event_equivalence": "NOT_VERIFIED",
            }):
        _fail("conflated hash domains")
    observed, known, expires = (candidate[k] for k in
                                ("observed_at", "known_at", "expires_at"))
    if (any(type(t) is not int for t in (observed, known, expires))
            or not now - 300 <= observed <= known <= now < expires <= now + 300):
        _fail("stale, future, expired or boolean timestamp")
    events = candidate["events"]
    if type(events) is not list or len(events) != 7:
        _fail("missing seven events")
    seen_evidence = set()
    for sequence, (event, row) in enumerate(zip(events, rows), 1):
        if type(event) is not dict or set(event) != _EVENT_FIELDS:
            _fail("event shape")
        if (type(event["sequence"]) is not int
                or event["sequence"] != sequence
                or event["source_event_id"] != row["source_event_id"]):
            _fail("foreign, missing or reordered event")
        evidence = event["evidence_id"]
        if type(evidence) is not str or not evidence or evidence in seen_evidence:
            _fail("missing or duplicate TEST_ONLY evidence reference")
        seen_evidence.add(evidence)
        digests = (event["payload_sha256"], event["full_event_sha256"])
        if any(type(h) is not str or not _HEX.fullmatch(h) for h in digests):
            _fail("invalid Core hash-shaped test data")
        if (digests[0] == digests[1]
                or any(h in (
                    row["acme_full_event_sha256"],
                    row["acme_local_payload_sha256"],
                    row["proposed_core_payload_sha256"],
                ) for h in digests)):
            _fail("ACME and Core domains conflated")
    if candidate["source_event_id"] not in result["source_event_ids"]:
        _fail("source event outside pinned replay")
    selected = next(e for e in events
                    if e["source_event_id"] == candidate["source_event_id"])
    if candidate["source_payload_hash"] != selected["payload_sha256"]:
        _fail("source payload not bound to selected event")
    unsigned = {k: v for k, v in candidate.items() if k != "receipt_sha256"}
    if candidate["receipt_sha256"] != core_receipt_digest(unsigned):
        _fail("Core-style digest mismatch")
    result["core_receipt_shape"] = "PASS_UNTRUSTED_TEST_INPUT_ONLY"
    result["reason"] = "STRUCTURE_ONLY_NOT_INDEPENDENT_CORE_AUTHORITY"
    return result


if __name__ == "__main__":
    print(json.dumps(inspect_untrusted_receipt(gen.replay(seed=20261018)),
                     sort_keys=True))
