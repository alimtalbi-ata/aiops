"""ACME-only, offline consumer for independently supplied Core seven-source readback.

This checks shape against the seven pinned SAN->Payments source IDs. It never
authenticates a Core transport, PG16 transaction, tenant, actor or GLPI rights.
A syntactically matching client-supplied receipt is not portable authority.
No network calls, Core writes, runtime IDs in output, or new receipt store.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from tools import acme_synthetic_source_authority_negative as negative
from tools import generate_acme_incidents as gen

SCHEMA = "aiops.acme.core-seven-readback-unknown-gate.v1"
CORE_SCHEMA = "aiops.core-canonical-seven-source-receipt.v1"
CORE_PAYLOAD_DOMAIN = "aiops.core-source-event-payload.v1"
CORE_FULL_DOMAIN = "aiops.core-full-run-event.v1"
FIXTURE = (gen.ROOT / "docs/customer-story" /
           "ACME-CORE-SEVEN-READBACK-UNKNOWN-2026-11-01.json")
HEX64 = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
REQUIRED = frozenset((
    "schema", "decision", "link_status", "source_preflight", "transport",
    "portable_signature", "issuer", "source_system", "tenant_id",
    "incident_id", "run_id", "glpi_instance_id", "ticket_id",
    "glpi_entity_id", "permission", "actor_issuer",
    "actor_subject_sha256", "source_event_id", "source_payload_hash",
    "observed_at", "known_at", "expires_at", "event_count",
    "hash_domains", "events", "source_proof_sha256", "receipt_sha256",
))
EVENT_KEYS = frozenset((
    "sequence", "source_event_id", "evidence_id",
    "payload_sha256", "full_event_sha256",
))


def build_fixture(manifest):
    """Redacted machine fixture: three LOCAL domains, no Core PG16 digest."""
    pinned = negative.build_negative_receipt(manifest)
    return {
        "schema": SCHEMA,
        "synthetic": True,
        "provenance": "SYNTHETIC_FIXTURE_ONLY",
        "seed": pinned["seed"],
        "graph_version": pinned["graph_version"],
        "source_replay_sha256": pinned["source_replay_sha256"],
        "core_readback_schema": CORE_SCHEMA,
        "core_readback": None,
        "core_pg16_authority": "UNKNOWN",
        "hash_domain_equivalence": "UNKNOWN",
        "event_count": 7,
        "events": [{
            "sequence": row["sequence"],
            "source_event_id": row["source_event_id"],
            "acme_full_event_sha256": row["acme_full_event_sha256"],
            "acme_local_payload_sha256": row["acme_local_payload_sha256"],
            "proposed_core_payload_sha256": row["proposed_core_payload_sha256"],
            "core_pg16_payload_sha256": None,
            "core_pg16_full_event_sha256": None,
            "mapping_status": "UNKNOWN",
        } for row in pinned["events"]],
        "runtime_authority": {
            "actor_subject": None, "tenant_id": None,
            "incident_id": None, "run_id": None,
            "glpi_ticket_id": None, "evidence_ids": [],
            "hitl_approval": None, "freshness": "UNKNOWN",
            "revocation": "UNKNOWN", "observed_impact": "UNKNOWN",
        },
        "itil_stages": {"count": 15, "status": "NOT_EXECUTED"},
        "checkpoints": {"count": 6, "status": "NOT_EXECUTED"},
        "result": "UNKNOWN",
        "publishable_to_core_or_glpi": False,
        "live_effects_authorized": False,
    }


def verify_fixture(manifest, candidate):
    expected = build_fixture(manifest)
    if type(candidate) is not dict or gen._canonical(candidate) != gen._canonical(expected):
        raise ValueError("foreign, missing or modified redacted fixture")
    return expected


def _hex(value):
    return type(value) is str and HEX64.fullmatch(value) is not None


def _reason(expected, supplied, expected_tenant, expected_actor_sha256, now):
    if supplied is None:
        return "NO_INDEPENDENT_CORE_READBACK"
    if type(supplied) is not dict:
        return "MALFORMED_CORE_READBACK"
    if supplied.get("schema") != CORE_SCHEMA:
        return "FOREIGN_CORE_SCHEMA"
    if set(supplied) != REQUIRED:
        return "MISSING_OR_UNEXPECTED_CORE_FIELDS"
    if (supplied["decision"] != "UNKNOWN" or
            supplied["link_status"] != "UNKNOWN" or
            supplied["source_preflight"] != "PASS_SYNTHETIC_ONLY" or
            supplied["transport"] != "TLS_AUTHENTICATED_NONPORTABLE" or
            supplied["portable_signature"] != "NONE"):
        return "UNTRUSTED_AUTHORITY_ASSERTION"
    domains = supplied["hash_domains"]
    if (type(domains) is not dict or domains != {
            "payload": CORE_PAYLOAD_DOMAIN,
            "full_event": CORE_FULL_DOMAIN,
            "acme_full_event_equivalence": "NOT_VERIFIED"}):
        return "FOREIGN_HASH_DOMAIN"
    events = supplied["events"]
    if type(events) is not list or len(events) != 7 or supplied["event_count"] != 7:
        return "MISSING_OR_EXTRA_EVENTS"
    pinned_ids = [r["source_event_id"] for r in expected["events"]]
    if (any(type(row) is not dict or set(row) != EVENT_KEYS for row in events) or
            [row["source_event_id"] for row in events] != pinned_ids or
            [row["sequence"] for row in events] != list(range(1, 8))):
        return "FOREIGN_DUPLICATE_OR_REORDERED_EVENTS"
    for row in events:
        if (type(row["evidence_id"]) is not str or not row["evidence_id"] or
                not _hex(row["payload_sha256"]) or
                not _hex(row["full_event_sha256"]) or
                row["payload_sha256"] == row["full_event_sha256"]):
            return "MISSING_EVIDENCE_OR_INVALID_CORE_HASH_DOMAINS"
    if (supplied["source_event_id"] not in pinned_ids or
            not _hex(supplied["source_payload_hash"]) or
            not _hex(supplied["source_proof_sha256"]) or
            not _hex(supplied["receipt_sha256"])):
        return "FOREIGN_SOURCE_OR_UNVERIFIABLE_DIGEST"
    for key in ("issuer", "source_system", "tenant_id", "incident_id",
                "run_id", "glpi_instance_id", "ticket_id",
                "glpi_entity_id", "permission", "actor_issuer"):
        if type(supplied[key]) is not str or not supplied[key]:
            return "MISSING_RUNTIME_SCOPE"
    if supplied["permission"] != "run:read" or not _hex(supplied["actor_subject_sha256"]):
        return "MISSING_ACTOR_OR_PERMISSION"
    if expected_tenant is not None and supplied["tenant_id"] != expected_tenant:
        return "FOREIGN_TENANT"
    if expected_actor_sha256 is not None and supplied["actor_subject_sha256"] != expected_actor_sha256:
        return "FOREIGN_ACTOR"
    if any(type(supplied[k]) is not int for k in ("observed_at", "known_at", "expires_at")):
        return "INVALID_FRESHNESS"
    if (not now - 300 <= supplied["observed_at"] <= supplied["known_at"] <= now or
            not now < supplied["expires_at"] <= now + 300):
        return "STALE_FUTURE_OR_EXPIRED"
    if expected_tenant is None or expected_actor_sha256 is None:
        return "NO_INDEPENDENT_ACTOR_TENANT_CONTEXT"
    # Even a shape match plus test-only expected context is NOT an
    # authenticated Core readback or evidence of revocation/audit.
    return "NO_INDEPENDENT_PG16_AUTHORITY"


def assess_readback(manifest, supplied=None, *, expected_tenant=None,
                    expected_actor_sha256=None, now=None):
    """Consume an untrusted supplied shape; return only redacted UNKNOWN.

    expected_tenant/actor_sha256 are comparisons, NOT an identity provider.
    Only Core can independently authenticate transport, ACL and PG16 data.
    """
    expected = build_fixture(manifest)
    if now is None:
        now = int(datetime.now(timezone.utc).timestamp())
    if type(now) is not int or now <= 0:
        raise ValueError("invalid independent clock")
    if expected_tenant is not None and (type(expected_tenant) is not str or not expected_tenant):
        raise ValueError("invalid comparison tenant")
    if expected_actor_sha256 is not None and not _hex(expected_actor_sha256):
        raise ValueError("invalid comparison actor digest")
    reason = _reason(expected, supplied, expected_tenant, expected_actor_sha256, now)
    return {
        "schema": SCHEMA,
        "result": "UNKNOWN",
        "reason": reason,
        "synthetic": True,
        "source_event_count": 7,
        "source_replay_sha256": expected["source_replay_sha256"],
        "core_readback": "UNAVAILABLE" if supplied is None else "UNVERIFIED",
        "core_pg16_authority": "UNKNOWN",
        "hash_domain_equivalence": "UNKNOWN",
        "tenant_id": None, "actor_subject": None,
        "incident_id": None, "run_id": None,
        "glpi_ticket_id": None, "evidence_ids": [],
        "hitl_approval": None, "freshness": "UNKNOWN",
        "revocation": "UNKNOWN",
        "itil_stages": {"count": 15, "status": "NOT_EXECUTED"},
        "checkpoints": {"count": 6, "status": "NOT_EXECUTED"},
        "publishable_to_core_or_glpi": False,
        "live_effects_authorized": False,
    }


def main():
    parser = argparse.ArgumentParser(description="Offline ACME Core readback UNKNOWN gate")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--emit", action="store_true")
    group.add_argument("--check", action="store_true")
    group.add_argument("--readback", type=Path, metavar="LOCAL_JSON")
    args = parser.parse_args()
    manifest = gen.replay(seed=20261018)
    if args.emit:
        print(json.dumps(build_fixture(manifest), sort_keys=True, indent=2,
                         ensure_ascii=True))
        return
    raw = FIXTURE.read_bytes()
    fixture = json.loads(raw.decode("utf-8"), object_pairs_hook=gen._unique_object)
    verify_fixture(manifest, fixture)
    supplied = None
    if args.readback is not None:
        with args.readback.open("rb") as stream:
            body = stream.read(65537)
        if len(body) > 65536:
            raise ValueError("oversized readback")
        supplied = json.loads(body.decode("utf-8"), object_pairs_hook=gen._unique_object)
    print(json.dumps(assess_readback(manifest, supplied), sort_keys=True))


if __name__ == "__main__":
    main()
