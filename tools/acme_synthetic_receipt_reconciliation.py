"""Fail-closed ACME fixture-to-Core receipt reconciliation contract (OFFLINE ONLY).

No HTTP requests, Core/GLPI writes, identity verification or runtime effects.
An optional *synthetic absence envelope* exercises readback shape/freshness
validation; it is never evidence of a Core request or an authenticated tenant.
Non-null runtime IDs require an independently authenticated adapter and are
rejected here rather than copied from untrusted caller-supplied JSON.
"""
import copy
from datetime import datetime
import re

from tools import acme_synthetic_itil_replay_verifier as verifier
from tools import generate_acme_incidents as gen

RECEIPT_AUTHORITIES = {
    "EVENT_ALERT": "SOURCE_EVENT",
    "GLPI_TICKET": "GLPI_AUTHENTICATED_READBACK",
    "CORE_INCIDENT": "CORE_AUTHENTICATED_READBACK",
    "CORE_RUN": "CORE_AUTHENTICATED_READBACK",
    "TWIN_IMPACT_CANDIDATE": "GOVERNED_TWIN",
    "ANALYST": "CORE_AI_LEDGER",
    "CRITIC": "CORE_AI_LEDGER",
    "EVIDENCE": "IMMUTABLE_EVIDENCE_SERVICE",
    "POLICY_PROPOSAL": "CORE_POLICY_LEDGER",
    "HITL_APPROVAL": "CORE_VERIFIED_HUMAN_LEDGER",
    "SIMULATE": "ISOLATED_EXECUTOR_RECEIPT",
    "POST_ACTION_VERIFICATION": "INDEPENDENT_VERIFICATION",
    "RESOLUTION": "CORE_INCIDENT_LEDGER",
    "REOPEN": "CORE_INCIDENT_LEDGER",
    "PROBLEM_KNOWLEDGE_CHANGE": "GOVERNED_ITSM_KNOWLEDGE",
}
RUNTIME_ID_FIELDS = ("tenant_id", "incident_id", "run_id", "glpi_ticket_id")
ABSENCE_ENVELOPE_KEYS = frozenset((
    "schema", "source", "test_partition", "tenant_id", "source_manifest_sha256",
    "source_dataset_sha256", "graph_version", "source_event_ids",
    "service_id", "ci_id", "synthetic_checked_at", "incident_id", "run_id",
    "glpi_ticket_id", "evidence_ids", "stage_receipts",
))


def synthetic_absence_envelope_offline(verified):
    """Construct an explicit test-only absence envelope, never an API receipt."""
    if type(verified) is not dict or verified.get("authority") != "OFFLINE_FIXTURE_ONLY":
        raise ValueError("untrusted synthetic verification source")
    return {
        "schema": "aiops.acme.synthetic-absence-readback.v1",
        "source": "OFFLINE_TEST_INPUT_NOT_CORE",
        "test_partition": verified["test_partition"],
        "tenant_id": None,
        "source_manifest_sha256": verified["source_manifest_sha256"],
        "source_dataset_sha256": verified["source_dataset_sha256"],
        "graph_version": verified["graph_version"],
        "source_event_ids": copy.deepcopy(verified["source_event_ids"]),
        "service_id": verified["service_id"],
        "ci_id": verified["ci_id"],
        "synthetic_checked_at": gen._stamp(120),
        "incident_id": None,
        "run_id": None,
        "glpi_ticket_id": None,
        "evidence_ids": [],
        "stage_receipts": [],
    }


def _validate_absence_envelope(envelope, verified, manifest):
    if type(envelope) is not dict or set(envelope) != ABSENCE_ENVELOPE_KEYS:
        raise ValueError("invalid or incomplete synthetic absence envelope")
    expected = synthetic_absence_envelope_offline(verified)
    for key in ("schema", "source", "test_partition", "tenant_id",
                "source_manifest_sha256", "source_dataset_sha256",
                "graph_version", "source_event_ids", "service_id", "ci_id"):
        if gen._canonical(envelope[key]) != gen._canonical(expected[key]):
            raise ValueError("foreign partition, source or replay in readback envelope")
    if (any(envelope[key] is not None for key in RUNTIME_ID_FIELDS) or
            type(envelope["evidence_ids"]) is not list or envelope["evidence_ids"] or
            type(envelope["stage_receipts"]) is not list or envelope["stage_receipts"]):
        raise ValueError("unverified runtime receipt or forged authority")
    stamp = envelope["synthetic_checked_at"]
    if type(stamp) is not str or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", stamp):
        raise ValueError("invalid synthetic readback clock")
    try:
        checked = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        last = datetime.fromisoformat(
            manifest["events"][-1]["known_at"].replace("Z", "+00:00"))
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid synthetic readback clock") from exc
    if not 0 <= (checked - last).total_seconds() <= 300:
        raise ValueError("stale or premature synthetic readback")


def reconcile_fixture_receipts_offline(manifest, *, test_partition="SYNTHETIC_TEST_PARTITION_A",
                                       deliveries=None, absence_envelope=None, candidate=None):
    """Return deterministic *requirements*, not attested Incident/Run receipts.

    The sole accepted envelope is a synthetic absence record. This boundary
    cannot establish actual Core/GLPI/Evidence identity, tenant authentication,
    HITL approval or execution. Any non-null receipt fails closed.
    """
    verified = verifier.verify_itil_replay_offline(
        manifest, test_partition=test_partition, deliveries=deliveries)
    if absence_envelope is not None:
        _validate_absence_envelope(absence_envelope, verified, manifest)
    stages = []
    for stage in verified["stages"]:
        name = stage["stage"]
        if name not in RECEIPT_AUTHORITIES:
            raise ValueError("unknown ITIL stage")
        stages.append({
            "stage": name,
            "required_authority": RECEIPT_AUTHORITIES[name],
            "source_event_id": stage["source_event_id"],
            "source_event_content_sha256": stage["source_event_content_sha256"],
            "source_ci_id": stage["source_ci_id"],
            "source_event_time": stage["source_event_time"],
            "runtime_checkpoint": stage["runtime_checkpoint"],
            "status": "NOT_EXECUTED",
            "receipt_id": None,
            "receipt_source": "UNKNOWN",
            "receipt_observed_at": None,
            "receipt_verified": False,
        })
    if len(stages) != 15 or len(RECEIPT_AUTHORITIES) != 15:
        raise ValueError("incomplete 15-stage receipt contract")
    checkpoints = copy.deepcopy(verified["checkpoints"])
    if (len(checkpoints) != 6 or any(
            c["status"] != "NOT_EXECUTED" or c["id"] is not None
            for c in checkpoints)):
        raise ValueError("untrusted runtime checkpoints")
    result = {
        "schema": "aiops.acme.synthetic-receipt-reconciliation.v1",
        "authority": "OFFLINE_FIXTURE_ONLY",
        "synthetic": True,
        "test_partition": verified["test_partition"],
        "test_partition_is_tenant_authority": False,
        "tenant_scope": "UNKNOWN",
        "seed": verified["seed"],
        "graph_version": verified["graph_version"],
        "source_dataset_sha256": verified["source_dataset_sha256"],
        "source_manifest_sha256": verified["source_manifest_sha256"],
        "canonical_replay_file_sha256": verified["canonical_replay_file_sha256"],
        "source_event_count": 7,
        "source_event_ids": copy.deepcopy(verified["source_event_ids"]),
        "service_id": verified["service_id"],
        "ci_id": verified["ci_id"],
        "blast_radius_candidate": copy.deepcopy(verified["blast_radius_candidate"]),
        "priority_confirmed": "UNKNOWN",
        "observed_impact": "UNKNOWN",
        "reconciliation_status": "NO_AUTHENTICATED_READBACK",
        "absence_envelope_checked": absence_envelope is not None,
        "absence_envelope_is_core_receipt": False,
        "runtime_readback": "NOT_EXECUTED",
        "runtime_references": copy.deepcopy(verified["runtime_receipts"]),
        "stages": stages,
        "checkpoints": checkpoints,
        "publishable_to_core_or_glpi": False,
        "live_effects_authorized": False,
    }
    if candidate is not None:
        if type(candidate) is not dict or gen._canonical(candidate) != gen._canonical(result):
            raise ValueError("untrusted receipt reconciliation projection")
    return result
