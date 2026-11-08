"""FS147 pre-dispatch coherence barrier; no IO or authorization side effects.

A matching link is only eligible for a fresh, transactional revalidation.
"""
from enum import Enum

from .fs147_launch_contract import LaunchSnapshot, LaunchStatus, classify_launch
from .fs147_snapshot_coherence import LinkIdentity, Coherence, classify_coherence


class BarrierStatus(str, Enum):
    DENIED = "DENIED"
    UNKNOWN = "UNKNOWN"
    NEEDS_HUMAN = "NEEDS_HUMAN"
    ELIGIBLE_FOR_REVALIDATION = "ELIGIBLE_FOR_REVALIDATION"


def classify_barrier(launch, *observed_links):
    """Compare independently observed identities before dispatch; fail closed."""
    launch_status = classify_launch(launch)
    if launch_status == LaunchStatus.DENIED:
        return BarrierStatus.DENIED
    if not isinstance(launch, LaunchSnapshot):
        return BarrierStatus.UNKNOWN
    identity = LinkIdentity(
        tenant_id=launch.tenant_id,
        idempotency_key=launch.idempotency_key,
        alert_fingerprint=launch.alert_fingerprint,
        incident_id=launch.incident_id,
        run_id=launch.run_id,
        evidence_id=launch.evidence_id,
        evidence_sha256=launch.evidence_sha256,
        glpi_ticket_id=launch.glpi_ticket_id,
        mode=launch.mode,
    )
    # Require at least one independent authoritative link observation.
    if not observed_links:
        return BarrierStatus.UNKNOWN
    coherence = classify_coherence(identity, *observed_links)
    if coherence == Coherence.DENIED:
        return BarrierStatus.DENIED
    if coherence != Coherence.MATCH:
        return BarrierStatus.UNKNOWN
    if launch_status == LaunchStatus.NEEDS_HUMAN:
        return BarrierStatus.NEEDS_HUMAN
    if launch_status != LaunchStatus.ELIGIBLE_FOR_REVALIDATION:
        return BarrierStatus.UNKNOWN
    return BarrierStatus.ELIGIBLE_FOR_REVALIDATION
