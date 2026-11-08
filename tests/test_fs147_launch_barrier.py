"""Pure regression tests: no DB, GLPI, Temporal or host interactions."""
from dataclasses import replace

from app.core.fs147_launch_barrier import BarrierStatus, classify_barrier
from app.core.fs147_launch_contract import LaunchSnapshot
from app.core.fs147_snapshot_coherence import LinkIdentity


def sample():
    s = LaunchSnapshot(
        mode="DEMO", tenant_id="tenant", idempotency_key="key",
        alert_fingerprint="fingerprint", incident_id="incident", run_id="run",
        evidence_id="evidence", evidence_sha256="a" * 64,
        glpi_ticket_id=147, ticket_exists_verified=True, policy="ALLOW",
        stop_auto=False, hitl="ACCEPTED", hitl_action_bound=True,
        ownership_verified=True, fencing_verified=True,
        temporal_state="WAITING_HUMAN", authoritative_read=True,
    )
    link = LinkIdentity(
        tenant_id=s.tenant_id, idempotency_key=s.idempotency_key,
        alert_fingerprint=s.alert_fingerprint, incident_id=s.incident_id,
        run_id=s.run_id, evidence_id=s.evidence_id,
        evidence_sha256=s.evidence_sha256, glpi_ticket_id=s.glpi_ticket_id,
        mode=s.mode,
    )
    return s, link


def test_repeatable_positive_preflight_is_not_dispatch():
    s, link = sample()
    assert [classify_barrier(s, link) for _ in range(3)] == [
        BarrierStatus.ELIGIBLE_FOR_REVALIDATION] * 3


def test_missing_or_malformed_independent_observation_unknown():
    s, link = sample()
    assert classify_barrier(s) == BarrierStatus.UNKNOWN
    assert classify_barrier(s, None) == BarrierStatus.UNKNOWN
    assert classify_barrier(s, replace(link, evidence_sha256="invalid")) == BarrierStatus.UNKNOWN


def test_identity_drift_and_ticket_mismatch_denied():
    s, link = sample()
    for bad in (replace(link, run_id="other"),
                replace(link, evidence_sha256="b" * 64),
                replace(link, glpi_ticket_id=146),
                replace(link, mode="LIVE")):
        assert classify_barrier(s, bad) == BarrierStatus.DENIED


def test_policy_live_and_stop_auto_denied():
    s, link = sample()
    for bad in (replace(s, mode="LIVE"), replace(s, policy="DENY"),
                replace(s, stop_auto=True), replace(s, glpi_ticket_id=146)):
        assert classify_barrier(bad, link) == BarrierStatus.DENIED


def test_human_pending_and_missing_authority_not_success():
    s, link = sample()
    assert classify_barrier(replace(s, hitl="PENDING"), link) == BarrierStatus.NEEDS_HUMAN
    assert classify_barrier(replace(s, authoritative_read=False), link) == BarrierStatus.UNKNOWN
    assert classify_barrier(replace(s, fencing_verified=False), link) == BarrierStatus.UNKNOWN
    assert classify_barrier(replace(s, hitl_action_bound=False), link) == BarrierStatus.DENIED
