"""Cross-plane Core admission regression matrix; synthetic, no network or mutations."""
from dataclasses import replace

import pytest

from app.core.core_lineage_gate import Receipt, Verdict, evaluate
from app.core.core_action_admission_gate import ActionProof, Admission, admit

BASE = Receipt(
    "tenant-a", "INC-147", "RUN-147", "DEMO", "EVENT-147",
    ("EVID-147",), "ANALYSIS-147", "CRITIC-147", "POLICY-147",
    "ALLOW", "ACTION-147", "RUN-147", "RUN-147", "GLPI",
    "147", True, "RUN-147", True,
)
PROOF = ActionProof(
    "tenant-a", "RUN-147", "ACTION-147", "sha256:abc",
    "ALLOW", "APPROVED", "ACTION-147", "sha256:abc",
    "worker-a", "worker-a", "42", "42",
    "RECONCILED_SAFE_TO_RESUME", True,
)


@pytest.mark.parametrize("field,value", [
    ("tenant_id", "tenant-b"),
    ("run_id", "RUN-OTHER"),
    ("action_id", "ACTION-OTHER"),
    ("hitl_action_id", "ACTION-OTHER"),
    ("hitl_action_digest", "sha256:other"),
    ("observed_owner_id", "worker-b"),
    ("observed_fencing_token", "41"),
])
def test_cross_plane_identity_conflicts_denied(field, value):
    assert admit(BASE, replace(PROOF, **{field: value})) == Admission.DENIED


@pytest.mark.parametrize("field,value", [
    ("evidence_ids", ()),
    ("analysis_id", None),
    ("critic_decision_id", None),
    ("policy_decision_id", None),
    ("itsm_readback_verified", False),
    ("external_ticket_id", None),
    ("portal_run_id", None),
])
def test_missing_cross_plane_receipt_never_admits(field, value):
    receipt = replace(BASE, **{field: value})
    assert evaluate(receipt).verdict == Verdict.UNKNOWN
    assert admit(receipt, PROOF) == Admission.UNKNOWN


@pytest.mark.parametrize("field,value", [
    ("policy_state", "DENY"),
    ("policy_state", "STOP_AUTO"),
])
def test_policy_refusal_has_priority_over_positive_proof(field, value):
    proof = replace(PROOF, **{field: value})
    assert admit(BASE, proof) == Admission.DENIED


@pytest.mark.parametrize("field,value", [
    ("temporal_reconciled", False),
    ("temporal_reconciled", None),
    ("temporal_state", "RUNNING"),
    ("fencing_token", None),
    ("observed_fencing_token", None),
])
def test_unverified_execution_evidence_never_admits(field, value):
    assert admit(BASE, replace(PROOF, **{field: value})) == Admission.UNKNOWN


def test_pending_hitl_and_live_refusal():
    assert admit(BASE, replace(PROOF, hitl_state="PENDING")) == Admission.NEEDS_HUMAN
    assert admit(replace(BASE, mode="LIVE"), replace(PROOF, hitl_state="PENDING")) == Admission.DENIED


def test_synthetic_positive_only_revalidation_not_execution():
    assert evaluate(BASE).verdict == Verdict.PASS
    assert admit(BASE, PROOF) == Admission.ELIGIBLE_FOR_REVALIDATION
