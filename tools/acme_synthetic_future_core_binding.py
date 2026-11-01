"""Fail-closed ACME future Core actor+tenant/source-hash readback contract.

This module validates only TEST_ONLY proposed *shapes*, never Core authority.
No HTTP, identity provider, Core/GLPI/Evidence calls, writes, model or effects.
A valid structural proposal remains UNAVAILABLE until an independently reviewed
Core adapter attests actor, tenant ACL, Incident/Run links and seven event hashes.
"""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import re

from tools import acme_synthetic_itil_replay_verifier as replay_verifier
from tools import generate_acme_incidents as gen

SCHEMA = "aiops.acme.future-core-actor-tenant-source-binding.v1"
SOURCE = "OFFLINE_TEST_INPUT_NOT_CORE"
MAX_AGE = timedelta(minutes=5)
UTC_STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
TEST_ID = re.compile(r"(?:INC|RUN)-TEST-ONLY-[A-Z0-9]+\Z")
TEST_PRINCIPAL = re.compile(r"TEST_ONLY_[A-Z0-9_]+\Z")
REQUIRED_AUTHORITY = (
    "INDEPENDENT_ACTOR_AUTHENTICATION",
    "SERVER_SIDE_TENANT_ACL",
    "INCIDENT_RUN_TENANT_AND_ACTOR_LINK",
    "SEVEN_IMMUTABLE_SOURCE_EVENT_HASH_LINKS",
    "SIGNED_OR_EQUIVALENT_TRUSTED_CORE_PROVENANCE",
    "FRESH_READBACK_AND_REVOCATION",
)


def pinned_event_bindings(manifest):
    """Canonical seven source-event digests, NOT Evidence-service receipts."""
    replay_verifier.verify_itil_replay_offline(manifest)
    return [
        {
            "source_event_id": e["source_event_id"],
            "source_event_content_sha256": hashlib.sha256(
                gen._canonical(e)).hexdigest(),
            "ci_id": e["ci_id"],
            "event_time": e["event_time"],
            "dedupe_key": e["dedupe_key"],
            "correlation_key": e["correlation_key"],
        }
        for e in manifest["events"]
    ]


def _test_identity(value):
    return type(value) is str and TEST_PRINCIPAL.fullmatch(value) is not None


def _validate_proposal(proposal, verified, expected_bindings, now):
    """Validate a disposable shape only. Never authenticate caller claims."""
    if type(proposal) is not dict or set(proposal) != {
            "schema", "source", "test_partition", "principal", "core", "attestation"}:
        raise ValueError("incomplete or unexpected readback proposal")
    if (proposal["schema"] != SCHEMA or proposal["source"] != SOURCE or
            proposal["test_partition"] != verified["test_partition"]):
        raise ValueError("foreign partition or forged Core source")
    principal = proposal["principal"]
    core = proposal["core"]
    attestation = proposal["attestation"]
    if type(principal) is not dict or set(principal) != {
            "tenant_id", "actor_subject"}:
        raise ValueError("missing or untrusted principal")
    if (not _test_identity(principal["tenant_id"]) or
            not _test_identity(principal["actor_subject"])):
        raise ValueError("principal is not explicitly TEST_ONLY")
    if type(core) is not dict or set(core) != {
            "incident_id", "run_id", "incident_tenant_id", "run_tenant_id",
            "incident_actor_subject", "run_actor_subject", "scenario_id",
            "service_id", "ci_id", "source_dataset_sha256",
            "source_manifest_sha256", "canonical_replay_file_sha256",
            "graph_version", "correlation_key", "source_event_bindings",
            "readback_at"}:
        raise ValueError("missing or unexpected Core binding field")
    for key, prefix in (("incident_id", "INC-"), ("run_id", "RUN-")):
        if (type(core[key]) is not str or
                TEST_ID.fullmatch(core[key]) is None or
                not core[key].startswith(prefix)):
            raise ValueError("runtime ID is not an explicit TEST_ONLY placeholder")
    if (core["incident_tenant_id"] != principal["tenant_id"] or
            core["run_tenant_id"] != principal["tenant_id"] or
            core["incident_actor_subject"] != principal["actor_subject"] or
            core["run_actor_subject"] != principal["actor_subject"]):
        raise ValueError("foreign actor or tenant Incident/Run binding")
    pinned = {
        "scenario_id": verified["scenario_id"],
        "service_id": verified["service_id"],
        "ci_id": verified["ci_id"],
        "source_dataset_sha256": verified["source_dataset_sha256"],
        "source_manifest_sha256": verified["source_manifest_sha256"],
        "canonical_replay_file_sha256": verified["canonical_replay_file_sha256"],
        "graph_version": verified["graph_version"],
        "correlation_key": verified["correlation"]["key"],
        "source_event_bindings": expected_bindings,
    }
    for key, value in pinned.items():
        if gen._canonical(core[key]) != gen._canonical(value):
            raise ValueError("foreign replay, source hash, graph or correlation")
    if type(attestation) is not dict or attestation != {
            "kind": "UNVERIFIED_TEST_INPUT",
            "actor_authenticated": False,
            "tenant_acl_qualified": False,
            "core_signature_verified": False}:
        raise ValueError("forged independent authority attestation")
    stamp = core["readback_at"]
    if type(stamp) is not str or UTC_STAMP.fullmatch(stamp) is None:
        raise ValueError("missing or non-UTC readback timestamp")
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid readback timestamp") from exc
    if not -timedelta(seconds=30) <= now - parsed <= MAX_AGE:
        raise ValueError("stale or future readback timestamp")


def verify_future_core_binding_offline(
        manifest, *, proposal=None,
        test_partition="SYNTHETIC_TEST_PARTITION_A", now=None):
    """Check pinned fixture and optionally a TEST_ONLY proposal, never receipts.

    A caller-supplied response or internal Bearer is not independent authority.
    Even a structurally matching proposal MUST NOT promote any runtime stage.
    """
    verified = replay_verifier.verify_itil_replay_offline(
        manifest, test_partition=test_partition)
    bindings = pinned_event_bindings(manifest)
    if len(bindings) != 7 or len({r["source_event_id"] for r in bindings}) != 7:
        raise ValueError("ambiguous seven-event source binding")
    if now is None:
        now = datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("invalid independent clock")
    now = now.astimezone(timezone.utc)
    if proposal is not None:
        _validate_proposal(proposal, verified, bindings, now)
    stages = copy.deepcopy(verified["stages"])
    checkpoints = copy.deepcopy(verified["checkpoints"])
    if (len(stages) != 15 or len(checkpoints) != 6 or
            any(s["status"] != "NOT_EXECUTED" or s["runtime_id"] is not None
                for s in stages) or
            any(c["status"] != "NOT_EXECUTED" or c["id"] is not None
                for c in checkpoints)):
        raise ValueError("untrusted runtime stage projection")
    return {
        "schema": SCHEMA,
        "synthetic": True,
        "authority": "OFFLINE_FIXTURE_ONLY",
        "result": "UNAVAILABLE",
        "reason": ("CORE_INDEPENDENT_ACTOR_TENANT_AUTHORITY_UNAVAILABLE"
                   if proposal is None else
                   "TEST_SHAPE_MATCH_ONLY_INDEPENDENT_AUTHORITY_UNAVAILABLE"),
        "test_partition": verified["test_partition"],
        "test_partition_is_tenant_authority": False,
        "proposal_shape_checked": proposal is not None,
        "required_independent_authority": list(REQUIRED_AUTHORITY),
        "seed": verified["seed"],
        "graph_version": verified["graph_version"],
        "canonical_replay_file_sha256": verified["canonical_replay_file_sha256"],
        "source_manifest_sha256": verified["source_manifest_sha256"],
        "source_dataset_sha256": verified["source_dataset_sha256"],
        "source_event_count": 7,
        "source_event_bindings": copy.deepcopy(bindings),
        "source_hash_is_evidence_receipt": False,
        "tenant_id": None, "actor_subject": None,
        "incident_id": None, "run_id": None,
        "glpi_ticket_id": None, "evidence_ids": [],
        "tenant_acl_qualified": False,
        "actor_authenticated": False,
        "source_event_binding_verified_by_core": False,
        "runtime_readback": "NOT_EXECUTED",
        "priority_confirmed": "UNKNOWN",
        "observed_impact": "UNKNOWN",
        "blast_radius_candidate": copy.deepcopy(verified["blast_radius_candidate"]),
        "stages": stages, "checkpoints": checkpoints,
        "publishable_to_core_or_glpi": False,
        "live_effects_authorized": False,
    }
