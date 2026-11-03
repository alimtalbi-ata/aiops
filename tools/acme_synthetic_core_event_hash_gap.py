"""ACME seven-event vs Core v1 single-event binding gap, offline only.

Core aiops.core-actor-run-event-binding.v1 readback covers ONE source
identifier/hash, whose upstream xref field is source_payload_hash. ACME pins
SEVEN hashes of entire event records. These digest domains are not equivalent.
This validator consumes TEST_ONLY shapes, never a Core receipt or auth proof.
"""
import copy
from datetime import datetime, timezone
import hashlib

from tools import acme_synthetic_future_core_binding as future
from tools import generate_acme_incidents as gen

SCHEMA = "aiops.acme.core-single-event-gap.v1"
CORE_SCHEMA = "aiops.core-actor-run-event-binding.v1"
TEST_SOURCE = "OFFLINE_TEST_INPUT_NOT_CORE"
HASH_SCOPE = "LOCAL_CANONICAL_PAYLOAD_SHA256_CANDIDATE"
FULL_EVENT_SCOPE = "ACME_CANONICAL_FULL_EVENT_SHA256"
TEST_PRINCIPAL = "TEST_ONLY_TENANT_A"
TEST_ACTOR = "TEST_ONLY_ACTOR_A"
_PROPOSAL_KEYS = frozenset((
    "schema", "source", "test_partition", "tenant_id", "actor_subject",
    "source_event_id", "source_event_hash", "source_event_content_sha256",
    "hash_scope", "observed_at", "known_at", "expires_at", "revoked",
    "verified", "authority",
))


def pinned_hash_domains(manifest):
    """Return local candidate hashes; neither digest is a Core receipt."""
    bindings = future.pinned_event_bindings(manifest)
    if len(bindings) != 7 or len({b["source_event_id"] for b in bindings}) != 7:
        raise ValueError("untrusted seven-event fixture")
    return [
        {
            "source_event_id": binding["source_event_id"],
            "full_event_sha256": binding["source_event_content_sha256"],
            "local_payload_sha256_candidate": hashlib.sha256(
                gen._canonical(event["payload"])).hexdigest(),
            "ci_id": binding["ci_id"],
            "event_time": binding["event_time"],
        }
        for binding, event in zip(bindings, manifest["events"])
    ]


def _clock(now):
    if now is None:
        return int(datetime.now(timezone.utc).timestamp())
    if type(now) is not int or now <= 0:
        raise ValueError("invalid independent clock")
    return now


def verify_single_event_core_gap_offline(
        manifest, *, proposals=None, test_partition="SYNTHETIC_TEST_PARTITION_A",
        expected_tenant=TEST_PRINCIPAL, expected_actor=TEST_ACTOR, now=None):
    """Fail closed on forged TEST_ONLY readback shapes; never return IDs.

    proposals are synthetic in-memory test shapes, NOT independently
    authenticated Core replies. Seven matching shapes remain UNAVAILABLE.
    """
    baseline = future.verify_future_core_binding_offline(
        manifest, test_partition=test_partition)
    domains = pinned_hash_domains(manifest)
    if (not future._test_identity(expected_tenant) or
            not future._test_identity(expected_actor)):
        raise ValueError("untrusted expected test-only actor or tenant")
    current = _clock(now)
    if proposals is None:
        proposals = []
    if type(proposals) is not list or len(proposals) > 7:
        raise ValueError("untrusted Core single-event test proposals")
    expected = {row["source_event_id"]: row for row in domains}
    matched = []
    for proof in proposals:
        if type(proof) is not dict or set(proof) != _PROPOSAL_KEYS:
            raise ValueError("missing or unexpected synthetic source proof fields")
        if (proof["schema"] != CORE_SCHEMA or proof["source"] != TEST_SOURCE or
                proof["test_partition"] != test_partition or
                proof["authority"] != "UNVERIFIED_SYNTHETIC_PROJECTION"):
            raise ValueError("foreign partition, schema or forged Core authority")
        if (proof["tenant_id"] != expected_tenant or
                proof["actor_subject"] != expected_actor or
                not future._test_identity(proof["tenant_id"]) or
                not future._test_identity(proof["actor_subject"])):
            raise ValueError("foreign actor or tenant")
        event_id = proof["source_event_id"]
        if type(event_id) is not str or event_id not in expected:
            raise ValueError("foreign source event")
        source = expected[event_id]
        if (proof["hash_scope"] != HASH_SCOPE or
                type(proof["source_event_hash"]) is not str or
                proof["source_event_hash"] != source["local_payload_sha256_candidate"] or
                type(proof["source_event_content_sha256"]) is not str or
                proof["source_event_content_sha256"] != source["full_event_sha256"]):
            raise ValueError("source hash domain mismatch or forged event digest")
        if proof["revoked"] is not False or proof["verified"] is not False:
            raise ValueError("revoked or forged authority assertion")
        observed, known, expires = (proof.get(k) for k in (
            "observed_at", "known_at", "expires_at"))
        if (any(type(x) is not int for x in (observed, known, expires)) or
                not current - 300 <= observed <= known <= current or
                not current < expires <= current + 300):
            raise ValueError("stale, future or invalid source readback")
        matched.append(event_id)
    canonical_order = [row["source_event_id"] for row in domains]
    if (len(set(matched)) != len(matched) or
            matched != [eid for eid in canonical_order if eid in set(matched)]):
        raise ValueError("duplicate or reordered source event readbacks")
    if len(baseline["stages"]) != 15 or len(baseline["checkpoints"]) != 6:
        raise ValueError("untrusted ITIL checkpoint count")
    return {
        "schema": SCHEMA,
        "synthetic": True,
        "result": "UNAVAILABLE",
        "reason": ("NO_INDEPENDENT_CORE_READBACK" if not matched else
                   "CORE_V1_SINGLE_EVENT_COVERAGE_ONLY" if len(matched) < 7 else
                   "SEVEN_TEST_SHAPES_ARE_NOT_CORE_AUTHORITY"),
        "core_schema": CORE_SCHEMA,
        "core_readback_cardinality": "ONE_SOURCE_EVENT_PER_RESPONSE",
        "core_source_hash_field": "source_event_hash",
        "core_xref_source_field": "source_payload_hash",
        "acme_full_event_hash_scope": FULL_EVENT_SCOPE,
        "core_hash_semantics_qualified": False,
        "hash_domain_mismatch": "FULL_EVENT_DIGEST_NOT_PROVEN_EQUAL_TO_CORE_PAYLOAD_HASH",
        "local_payload_digest_is_core_receipt": False,
        "test_partition": test_partition,
        "test_partition_is_tenant_authority": False,
        "source_event_count": 7,
        "synthetic_shape_coverage": len(matched),
        "source_event_hash_domains": copy.deepcopy(domains),
        "source_manifest_sha256": baseline["source_manifest_sha256"],
        "canonical_replay_file_sha256": baseline["canonical_replay_file_sha256"],
        "seed": baseline["seed"],
        "graph_version": baseline["graph_version"],
        "tenant_id": None, "actor_subject": None,
        "incident_id": None, "run_id": None, "glpi_ticket_id": None,
        "evidence_ids": [],
        "actor_authenticated": False,
        "tenant_acl_qualified": False,
        "source_event_binding_verified_by_core": False,
        "runtime_readback": "NOT_EXECUTED",
        "observed_impact": "UNKNOWN",
        "priority_confirmed": "UNKNOWN",
        "stages": copy.deepcopy(baseline["stages"]),
        "checkpoints": copy.deepcopy(baseline["checkpoints"]),
        "publishable_to_core_or_glpi": False,
        "live_effects_authorized": False,
    }
