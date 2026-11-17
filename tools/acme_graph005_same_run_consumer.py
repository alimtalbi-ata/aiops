"""Fail-closed ACME graph-005 same-Run SOURCE consumer.

Only Core's separately configured HTTPS source client can fetch a nonportable
readback. An offline JSON receipt, even with matching SHA256, never authenticates
PG16, a human IdP, GLPI rights, HITL, or a runtime replay fence. No writes.
"""
from __future__ import annotations

import hashlib
import json
import re

from tools import acme_synthetic_pg16_seven_bridge as bridge
from tools import acme_synthetic_https_seven_concordance as twin
from tools import generate_acme_incidents as gen

SCHEMA = "aiops.acme.graph005-interleaved-source-consumer.v1"
RECEIPT_SCHEMA = "aiops.core-canonical-seven-source-receipt.v1"
RECEIPT_DOMAIN = "aiops.core-canonical-seven-receipt-hash.v1"
CORE_DOMAINS = {
    "payload": "aiops.core-source-event-payload.v1",
    "full_event": "aiops.core-full-run-event.v1",
    "acme_full_event_equivalence": "NOT_VERIFIED",
}
PHYSICAL_SEQUENCES = (1, 2, 4, 5, 6, 8, 9)
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
EVENT_ID = re.compile(r"SYN-EVT-[0-9A-F]{20}\Z")
SCOPE = ("tenant_id", "incident_id", "run_id", "glpi_instance_id",
         "ticket_id", "glpi_entity_id", "permission")
RECEIPT_KEYS = frozenset((
    "schema", "decision", "link_status", "source_preflight", "transport",
    "portable_signature", "issuer", "source_system", "tenant_id",
    "incident_id", "run_id", "glpi_instance_id", "ticket_id",
    "glpi_entity_id", "permission", "actor_issuer",
    "actor_subject_sha256", "source_event_id", "source_payload_hash",
    "observed_at", "known_at", "expires_at", "event_count",
    "hash_domains", "events", "source_proof_sha256", "receipt_sha256",
))
ROW_KEYS = frozenset(("sequence", "source_event_id", "evidence_id",
                      "payload_sha256", "full_event_sha256"))


def _digest(domain, value):
    raw = json.dumps({"schema": domain, "event": value}, sort_keys=True,
                     separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def _base(manifest):
    local = bridge.build_receipt(manifest)
    impact = local["twin_impact"]
    if (local["graph_version"] != gen.SEED_GIT_BLOB
            or local["source_event_count"] != 7
            or len({r["source_event_id"] for r in local["events"]}) != 7
            or tuple(impact["path_node_ids"]) != twin.PATH_NODES
            or tuple(impact["path_edge_ids"]) != twin.PATH_EDGES
            or impact["source_ci_id"] != "ACME-SAN-FABRIC-A"
            or impact["selected_service_id"] != "ACME-SVC-PAYMENTS"
            or impact["candidate_ci_count"] != 10):
        raise ValueError("unpinned graph005 source or Twin")
    return local, {
        "schema": SCHEMA, "synthetic": True,
        "source_concordance": "UNKNOWN",
        "source_reason": "NO_INDEPENDENT_CORE_READBACK",
        "core_https_runtime_authentication": "NOT_ATTESTED",
        "core_pg16_authority": "UNKNOWN", "actor_idp_authority": "UNKNOWN",
        "tenant_actor_scope": "UNKNOWN", "freshness": "UNKNOWN",
        "revocation": "UNKNOWN", "durable_replay_fence": "NOT_ATTESTED",
        "runtime_incident_id": None, "runtime_run_id": None,
        "glpi_human_allow": "UNKNOWN", "hitl_approval": "UNKNOWN",
        "observed_payments_outage": "UNKNOWN",
        "graph_version": local["graph_version"],
        "source_replay_sha256": local["source_replay_sha256"],
        "source_ordinals": list(range(1, 8)),
        "physical_run_sequences": list(PHYSICAL_SEQUENCES),
        "events": [{
            "source_ordinal": n, "physical_run_sequence": PHYSICAL_SEQUENCES[n - 1],
            "source_event_id": row["source_event_id"],
            "acme_fixture_full_sha256": row["acme_full_event_sha256"],
            "acme_fixture_payload_sha256": row["acme_local_payload_sha256"],
            "core_full_event_sha256": None, "core_payload_sha256": None,
            "domain_equivalence": "UNKNOWN",
        } for n, row in enumerate(local["events"], 1)],
        "twin_impact": impact,
        "itil_stages": {"verified": 0, "not_executed": 15, "status": "NOT_EXECUTED"},
        "human_checkpoints": {"verified": 0, "not_executed": 6,
                              "status": "NOT_EXECUTED"},
        "result": "UNKNOWN", "publishable_to_core_or_glpi": False,
        "live_effects_authorized": False, "release_stable": "NO_GO",
    }


def _validate(receipt, local, *, claims, expected, record, source_issuer, now):
    if (type(now) is not int or now <= 0 or type(claims) is not dict
            or type(expected) is not dict or type(record) is not dict
            or type(source_issuer) is not str or not source_issuer
            or any(type(claims.get(k)) is not str or not claims[k]
                   for k in ("sub", "iss"))
            or type(claims.get("exp")) is not int or claims["exp"] <= now
            or claims["iss"] == source_issuer
            or any(type(expected.get(k)) is not str or not expected[k]
                   for k in SCOPE)
            or expected["permission"] != "run:read"):
        return "UNPINNED_ACTOR_SOURCE_OR_RUNTIME_SCOPE"
    if (type(record.get("source_event_id")) is not str
            or not EVENT_ID.fullmatch(record["source_event_id"])
            or record["source_event_id"] not in
            {r["source_event_id"] for r in local["events"]}
            or type(record.get("source_payload_hash")) is not str
            or not HEX64.fullmatch(record["source_payload_hash"])
            or any(record.get(k) != expected[k] for k in
                   ("tenant_id", "incident_id", "run_id", "glpi_entity_id"))):
        return "FOREIGN_OR_UNPINNED_SOURCE_RECORD"
    if type(receipt) is not dict or set(receipt) != RECEIPT_KEYS:
        return "MISSING_OR_EXTRA_CORE_RECEIPT_FIELDS"
    if (receipt["schema"] != RECEIPT_SCHEMA
            or receipt["decision"] != "UNKNOWN"
            or receipt["link_status"] != "UNKNOWN"
            or receipt["source_preflight"] != "PASS_SYNTHETIC_ONLY"
            or receipt["transport"] != "TLS_AUTHENTICATED_NONPORTABLE"
            or receipt["portable_signature"] != "NONE"
            or receipt["source_system"] != "CORE_CANONICAL_READBACK"
            or receipt["issuer"] != source_issuer
            or receipt["actor_issuer"] != claims["iss"]
            or receipt["actor_subject_sha256"] !=
            hashlib.sha256(claims["sub"].encode("utf-8")).hexdigest()
            or any(receipt[k] != expected[k] for k in SCOPE)
            or receipt["source_event_id"] != record["source_event_id"]
            or receipt["source_payload_hash"] != record["source_payload_hash"]
            or receipt["hash_domains"] != CORE_DOMAINS):
        return "FOREIGN_ACTOR_TENANT_ISSUER_OR_HASH_DOMAIN"
    if (any(type(receipt[k]) is not int for k in
            ("observed_at", "known_at", "expires_at"))
            or not now - 300 <= receipt["observed_at"] <=
            receipt["known_at"] <= now < receipt["expires_at"] <=
            min(now + 300, claims["exp"])):
        return "STALE_FUTURE_EXPIRED_OR_REVOKED_SCOPE"
    rows = receipt["events"]
    if type(rows) is not list or len(rows) != 7 or receipt["event_count"] != 7:
        return "MISSING_OR_EIGHTH_SOURCE"
    evidence_ids = set()
    full_hashes, payload_hashes = set(), set()
    record_matches = 0
    for n, (row, pinned) in enumerate(zip(rows, local["events"]), 1):
        if (type(row) is not dict or set(row) != ROW_KEYS
                or type(row["sequence"]) is not int
                or row["sequence"] != PHYSICAL_SEQUENCES[n - 1]
                or row["source_event_id"] != pinned["source_event_id"]
                or not EVENT_ID.fullmatch(row["source_event_id"])
                or type(row["evidence_id"]) is not str
                or not row["evidence_id"]
                or row["evidence_id"] in evidence_ids
                or any(type(row[k]) is not str or not HEX64.fullmatch(row[k])
                       for k in ("payload_sha256", "full_event_sha256"))
                or row["payload_sha256"] == row["full_event_sha256"]
                or row["payload_sha256"] in payload_hashes
                or row["full_event_sha256"] in full_hashes):
            return "FOREIGN_REORDERED_DUPLICATE_OR_FORGED_SOURCE"
        evidence_ids.add(row["evidence_id"])
        full_hashes.add(row["full_event_sha256"])
        payload_hashes.add(row["payload_sha256"])
        if row["source_event_id"] == record["source_event_id"]:
            record_matches += 1
            if row["payload_sha256"] != record["source_payload_hash"]:
                return "SOURCE_RECORD_PAYLOAD_DOMAIN_MISMATCH"
    if record_matches != 1:
        return "FOREIGN_SOURCE_RECORD"
    if (type(receipt["source_proof_sha256"]) is not str
            or not HEX64.fullmatch(receipt["source_proof_sha256"])
            or type(receipt["receipt_sha256"]) is not str
            or not HEX64.fullmatch(receipt["receipt_sha256"])
            or receipt["receipt_sha256"] != _digest(
                RECEIPT_DOMAIN, {k: v for k, v in receipt.items()
                                 if k != "receipt_sha256"})):
        return "FORGED_OR_CORRUPT_RECEIPT_HASH"
    return None


def consume(manifest, *, receipt=None, claims=None, expected=None, record=None,
            source_issuer=None, now=None, seen_receipt_hashes=None):
    """Structural comparison only; caller must not treat receipt as auth.

    seen_receipt_hashes is an in-process test guard. It is NOT durable
    revocation/nonce authority. Without it, fail closed.
    """
    local, result = _base(manifest)
    if receipt is None:
        return result
    reason = _validate(receipt, local, claims=claims, expected=expected,
                       record=record, source_issuer=source_issuer, now=now)
    if reason is not None:
        result["source_reason"] = reason
        return result
    if type(seen_receipt_hashes) is not set:
        result["source_reason"] = "REPLAY_GUARD_UNAVAILABLE"
        return result
    digest = receipt["receipt_sha256"]
    if digest in seen_receipt_hashes:
        result["source_reason"] = "REPLAYED_CORE_RECEIPT"
        return result
    seen_receipt_hashes.add(digest)
    result["source_reason"] = "NONPORTABLE_SOURCE_SHAPE_ONLY"
    result["source_concordance"] = "CONSISTENT_UNTRUSTED"
    result["tenant_actor_scope"] = "SOURCE_CLAIM_CONSISTENT_NOT_IDP_AUTHORITY"
    result["freshness"] = "SOURCE_CLAIM_IN_WINDOW_NOT_RUNTIME_ATTESTED"
    result["revocation"] = "SOURCE_CLAIM_ONLY_NOT_DURABLE"
    for row, core in zip(result["events"], receipt["events"]):
        row["core_full_event_sha256"] = core["full_event_sha256"]
        row["core_payload_sha256"] = core["payload_sha256"]
        row["domain_equivalence"] = "DISTINCT_DOMAINS_NOT_EQUIVALENT"
    return result


def consume_via_core_https(manifest, *, claims, expected, record,
                           source_issuer, now, seen_receipt_hashes):
    """Call Core's independently configured HTTPS/TLS service preflight.

    Core owns transport credentials and PG16. The returned digest is not a
    portable signature, and claims are not a human IdP/GLPI attestation.
    """
    from core.actor_canonical_seven_source import canonical_seven_source_receipt
    receipt = canonical_seven_source_receipt(claims, expected, record, now)
    result = consume(manifest, receipt=receipt if isinstance(receipt, dict) else None,
                     claims=claims, expected=expected, record=record,
                     source_issuer=source_issuer, now=now,
                     seen_receipt_hashes=seen_receipt_hashes)
    if result["source_concordance"] == "CONSISTENT_UNTRUSTED":
        result["core_https_runtime_authentication"] = (
            "CORE_SOURCE_CLIENT_PREFLIGHT_NONPORTABLE")
    return result


# A projection of the Worker #340 disposable harness, NOT a production
# Worker/Temporal/GLPI readback. Only the independently fetched Core SOURCE
# receipt can be compared here; these Worker rows have no portable authority.
WORKER_HARNESS_PROJECTION = {
    3: ("DGX_ANALYST", "PASS", None, "worker-graph005-analyst"),
    7: ("VERIFY", "BLOCKED", "UNVERIFIED", "worker-graph005-verify"),
    10: ("HITL", "BLOCKED", "REJECT", "worker-graph005-reject"),
}
RUN_PROJECTION_KEYS = frozenset((
    "sequence", "run_id", "incident_id", "tenant_id", "stage",
    "event_type", "status", "decision", "event_key", "source_event_id",
    "payload_sha256", "full_event_sha256",
))


def consume_joined_worker_projection(
        manifest, *, run_events=None, receipt=None, claims=None, expected=None,
        record=None, source_issuer=None, now=None, seen_receipt_hashes=None):
    """Fail-closed *structural* join of seven Core SOURCE and Worker harness rows.

    run_events is a caller-provided redacted projection, not an authenticated
    full-Run API. This method MUST NOT attest real Worker execution, terminal
    014, outbox replay, IdP/GLPI rights or a human decision, even on a match.
    """
    result = consume(
        manifest, receipt=receipt, claims=claims, expected=expected,
        record=record, source_issuer=source_issuer, now=now,
        seen_receipt_hashes=seen_receipt_hashes)
    result.update({
        "worker_projection_concordance": "UNKNOWN",
        "worker_projection_reason": "NO_INDEPENDENT_WORKER_RUN_READBACK",
        "worker_harness_rows_shape_matched": 0,
        "worker_production_authority": "UNKNOWN",
        "core_terminal_014_joined": "NOT_ATTESTED",
        "core_outbox_replay_joined": "NOT_ATTESTED",
    })
    if result["source_concordance"] != "CONSISTENT_UNTRUSTED":
        result["worker_projection_reason"] = "SOURCE_NOT_CONCORDANT"
        return result
    if type(run_events) is not list or len(run_events) != 10:
        result["worker_projection_reason"] = "MISSING_OR_EXTRA_RUN_EVENTS"
        return result
    if type(expected) is not dict or type(receipt) is not dict:
        result["worker_projection_reason"] = "MISSING_RUNTIME_SCOPE"
        return result

    source_pos = {seq: i for i, seq in enumerate(PHYSICAL_SEQUENCES)}
    payload_hashes, full_hashes = set(), set()
    for sequence, row in enumerate(run_events, 1):
        if (type(row) is not dict or set(row) != RUN_PROJECTION_KEYS
                or type(row["sequence"]) is not int
                or row["sequence"] != sequence
                or any(row[k] != expected[k] for k in (
                    "tenant_id", "incident_id", "run_id"))
                or any(type(row[k]) is not str or not HEX64.fullmatch(row[k])
                       for k in ("payload_sha256", "full_event_sha256"))
                or row["payload_sha256"] == row["full_event_sha256"]
                or row["payload_sha256"] in payload_hashes
                or row["full_event_sha256"] in full_hashes):
            result["worker_projection_reason"] = "FOREIGN_REPLAYED_OR_FORGED_RUN_ROW"
            return result
        payload_hashes.add(row["payload_sha256"])
        full_hashes.add(row["full_event_sha256"])
        if sequence in source_pos:
            core = receipt["events"][source_pos[sequence]]
            if (row["stage"] != "SOURCE"
                    or row["event_type"] != "OBSERVED"
                    or row["status"] != "PASS"
                    or row["decision"] is not None
                    or row["source_event_id"] != core["source_event_id"]
                    or row["event_key"] != core["source_event_id"]
                    or row["payload_sha256"] != core["payload_sha256"]
                    or row["full_event_sha256"] != core["full_event_sha256"]):
                result["worker_projection_reason"] = "SOURCE_RUN_HASH_OR_ID_MISMATCH"
                return result
        else:
            stage, status, decision, key = WORKER_HARNESS_PROJECTION[sequence]
            if (row["stage"] != stage
                    or row["event_type"] != "WORKFLOW_OBSERVATION"
                    or row["status"] != status
                    or row["decision"] != decision
                    or row["event_key"] != key
                    or row["source_event_id"] is not None):
                result["worker_projection_reason"] = "UNTRUSTED_WORKER_STAGE_OR_APPROVAL"
                return result

    result["worker_projection_concordance"] = "CONSISTENT_UNTRUSTED"
    result["worker_projection_reason"] = "DISPOSABLE_HARNESS_SHAPE_ONLY"
    result["worker_harness_rows_shape_matched"] = 3
    return result
