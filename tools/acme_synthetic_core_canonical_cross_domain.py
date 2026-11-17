"""Offline ACME/Core canonical source-event hash cross-contract fixture.

The Core PG16 disposable test hashes {"schema": CORE_PAYLOAD_SCHEMA,
"event": event} using compact sorted ASCII JSON. This module applies that
serialization to an explicitly PROPOSED ACME projection. It does NOT claim
that Core ingested these seven events or that the Core test-only event shape
equals the ACME full-event domain. No network, receipt, or runtime ID.
"""
import copy
import hashlib

from tools import acme_synthetic_core_event_hash_gap as gap
from tools import acme_synthetic_future_core_binding as future
from tools import generate_acme_incidents as gen

SCHEMA = "aiops.acme.core-source-canonical-cross-domain.v1"
CORE_PAYLOAD_SCHEMA = "aiops.core-source-event-payload.v1"
CORE_WIRE_SCHEMA = "aiops.core-actor-run-event-binding.v1"
SOURCE = "OFFLINE_TEST_INPUT_NOT_CORE"
AUTHORITY = "UNVERIFIED_SYNTHETIC_PROJECTION"
TEST_TENANT = "TEST_ONLY_TENANT_A"
TEST_ACTOR = "TEST_ONLY_ACTOR_A"
TEST_PARTITION = "SYNTHETIC_TEST_PARTITION_A"
_PROPOSAL_KEYS = frozenset((
    "schema", "source", "authority", "test_partition", "tenant_id",
    "actor_subject", "observed_at", "known_at", "expires_at", "revoked",
    "verified", "bindings",
))


def proposed_cross_domain_rows(manifest):
    """Seven immutable local comparisons, never Core/Evidence receipts."""
    pinned = gap.pinned_hash_domains(manifest)  # verifies canonical replay
    if len(pinned) != 7 or len(manifest["events"]) != 7:
        raise ValueError("untrusted seven-event replay")
    rows = []
    for sequence, (event, source) in enumerate(zip(manifest["events"], pinned), 1):
        if event["source_event_id"] != source["source_event_id"]:
            raise ValueError("event source order mismatch")
        # Runtime ownership and Core's test-only 'metric' are deliberately
        # unknown. The ACME-only fields make this a proposed projection, NOT
        # the event_at(i) shape in the Core disposable PG16 test.
        proposed = {
            "source_event_id": event["source_event_id"],
            "sequence": sequence,
            "tenant_id": None,
            "incident_id": None,
            "run_id": None,
            "ticket_id": None,
            "glpi_entity_id": None,
            "metric": None,
            "synthetic": True,
            "acme_ci_id": event["ci_id"],
            "acme_event_time": event["event_time"],
            "acme_payload": copy.deepcopy(event["payload"]),
        }
        core_candidate = hashlib.sha256(gen._canonical({
            "schema": CORE_PAYLOAD_SCHEMA, "event": proposed,
        })).hexdigest()
        rows.append({
            "source_event_id": event["source_event_id"],
            "sequence": sequence,
            "acme_full_event_sha256": source["full_event_sha256"],
            "acme_payload_sha256_candidate": source["local_payload_sha256_candidate"],
            "proposed_core_wrapped_event_sha256": core_candidate,
            "proposed_core_event": proposed,
            "mapping_authority": "LOCAL_PROPOSAL_NOT_CORE_EVENT",
        })
    if len({r["source_event_id"] for r in rows}) != 7:
        raise ValueError("ambiguous source event IDs")
    return rows


def _check_test_proposal(proposal, rows, *, now, partition, tenant, actor):
    if type(proposal) is not dict or set(proposal) != _PROPOSAL_KEYS:
        raise ValueError("missing or unexpected test-only proposal fields")
    if (proposal["schema"] != SCHEMA or proposal["source"] != SOURCE or
            proposal["authority"] != AUTHORITY or
            proposal["test_partition"] != partition):
        raise ValueError("forged source, schema or foreign partition")
    if (proposal["tenant_id"] != tenant or proposal["actor_subject"] != actor or
            not future._test_identity(proposal["tenant_id"]) or
            not future._test_identity(proposal["actor_subject"])):
        raise ValueError("foreign or unauthenticated test actor/tenant")
    if proposal["revoked"] is not False or proposal["verified"] is not False:
        raise ValueError("revoked or forged Core authority")
    observed, known, expires = (proposal[k] for k in
                                ("observed_at", "known_at", "expires_at"))
    if (any(type(v) is not int for v in (observed, known, expires)) or
            not now - 300 <= observed <= known <= now or
            not now < expires <= now + 300):
        raise ValueError("stale, future or expired test proposal")
    candidate = proposal["bindings"]
    if type(candidate) is not list or len(candidate) != 7:
        raise ValueError("missing seven source-event mappings")
    # Canonical bytes reject bool/int aliasing, nested tampering, missing
    # fields, duplicates, swapped hash domains and reordered source events.
    if gen._canonical(candidate) != gen._canonical(rows):
        raise ValueError("foreign, reordered or forged source-event mapping")


def verify_core_canonical_cross_domain_offline(
        manifest, *, proposal=None, now=None, test_partition=TEST_PARTITION,
        expected_tenant=TEST_TENANT, expected_actor=TEST_ACTOR):
    """Validate proposed mapping without granting ANY Core runtime authority.

    Even seven matching synthetic mappings remain UNAVAILABLE. The Core v1
    wire is single-event and its disposable PG16 hash schema is test-only.
    """
    if (not future._test_identity(expected_tenant) or
            not future._test_identity(expected_actor) or
            type(test_partition) is not str or
            not test_partition.startswith("SYNTHETIC_TEST_PARTITION_")):
        raise ValueError("untrusted test-only actor, tenant or partition")
    current = gap._clock(now)
    baseline = gap.verify_single_event_core_gap_offline(
        manifest, test_partition=test_partition, now=current)
    rows = proposed_cross_domain_rows(manifest)
    if proposal is not None:
        _check_test_proposal(
            proposal, rows, now=current, partition=test_partition,
            tenant=expected_tenant, actor=expected_actor)
    if (len(baseline["stages"]) != 15 or len(baseline["checkpoints"]) != 6 or
            any(s["status"] != "NOT_EXECUTED" or s["runtime_id"] is not None
                for s in baseline["stages"]) or
            any(c["status"] != "NOT_EXECUTED" or c["id"] is not None
                for c in baseline["checkpoints"])):
        raise ValueError("untrusted ITIL runtime projection")
    return {
        "schema": SCHEMA,
        "synthetic": True,
        "result": "UNAVAILABLE",
        "reason": ("NO_INDEPENDENT_SEVEN_EVENT_CORE_READBACK" if proposal is None
                   else "SEVEN_LOCAL_HASH_PROPOSALS_NOT_CORE_AUTHORITY"),
        "source": "ACME_OFFLINE_CROSS_CONTRACT_FIXTURE",
        "core_payload_schema": CORE_PAYLOAD_SCHEMA,
        "core_wire_schema": CORE_WIRE_SCHEMA,
        "core_wire_cardinality": "ONE_EVENT_PER_RESPONSE",
        "core_disposable_hash_domain": "TEST_ONLY_NOT_RUNTIME_QUALIFIED",
        "core_serialization": "SHA256_ASCII_SORTED_COMPACT_JSON_SCHEMA_AND_EVENT",
        "acme_full_event_domain": "SHA256_ACME_CANONICAL_FULL_EVENT",
        "acme_payload_domain": "SHA256_ACME_CANONICAL_PAYLOAD",
        "cross_domain_mapping": {
            "source_event_id": "ACME_EVENT.source_event_id",
            "sequence": "ONE_BASED_CANONICAL_REPLAY_ORDER",
            "synthetic": "TRUE_FROM_PINNED_FIXTURE",
            "acme_ci_id": "ACME_EVENT.ci_id",
            "acme_event_time": "ACME_EVENT.event_time",
            "acme_payload": "ACME_EVENT.payload",
            "tenant_id": "UNKNOWN_NULL",
            "incident_id": "UNKNOWN_NULL",
            "run_id": "UNKNOWN_NULL",
            "ticket_id": "UNKNOWN_NULL",
            "glpi_entity_id": "UNKNOWN_NULL",
            "metric": "UNKNOWN_NULL_NOT_CORE_TEST_METRIC",
        },
        "hash_domains_equivalent": False,
        "core_runtime_source_serialization_qualified": False,
        "seven_event_readback_authenticated": False,
        "actor_authenticated": False,
        "tenant_acl_qualified": False,
        "test_partition_is_tenant_authority": False,
        "proposal_shape_checked": proposal is not None,
        "source_event_count": 7,
        "source_event_hash_domains": copy.deepcopy(rows),
        "canonical_replay_file_sha256": baseline["canonical_replay_file_sha256"],
        "source_manifest_sha256": baseline["source_manifest_sha256"],
        "seed": baseline["seed"],
        "graph_version": baseline["graph_version"],
        "tenant_id": None, "actor_subject": None,
        "incident_id": None, "run_id": None, "glpi_ticket_id": None,
        "evidence_ids": [],
        "observed_impact": "UNKNOWN",
        "priority_confirmed": "UNKNOWN",
        "runtime_readback": "NOT_EXECUTED",
        "stages": copy.deepcopy(baseline["stages"]),
        "checkpoints": copy.deepcopy(baseline["checkpoints"]),
        "publishable_to_core_or_glpi": False,
        "live_effects_authorized": False,
    }
