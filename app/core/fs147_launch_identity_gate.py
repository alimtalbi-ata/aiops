"""FS147 strict identity preflight. Pure: no IO, launch or Temporal signal.

A launch snapshot with syntactically invalid correlation must never become
eligible even if adapter-supplied verification flags are True.
"""
from enum import Enum

from .fs147_immutable_link import Link, LinkDecision, classify_link
from .fs147_launch_contract import LaunchSnapshot, LaunchStatus, classify_launch


class IdentityLaunchStatus(str, Enum):
    DENIED = "DENIED"
    UNKNOWN = "UNKNOWN"
    NEEDS_HUMAN = "NEEDS_HUMAN"
    ELIGIBLE_FOR_REVALIDATION = "ELIGIBLE_FOR_REVALIDATION"


def classify_identity_launch(snapshot):
    """A positive result is only a candidate for fresh transactional checks."""
    if not isinstance(snapshot, LaunchSnapshot):
        return IdentityLaunchStatus.UNKNOWN
    status = classify_launch(snapshot)
    if status == LaunchStatus.DENIED:
        return IdentityLaunchStatus.DENIED
    link = Link(
        tenant_id=snapshot.tenant_id,
        idempotency_key=snapshot.idempotency_key,
        alert_fingerprint=snapshot.alert_fingerprint,
        incident_id=snapshot.incident_id,
        run_id=snapshot.run_id,
        evidence_id=snapshot.evidence_id,
        evidence_sha256=snapshot.evidence_sha256,
        glpi_ticket_id=snapshot.glpi_ticket_id,
        mode=snapshot.mode,
    )
    identity = classify_link(link)
    if identity == LinkDecision.DENIED:
        return IdentityLaunchStatus.DENIED
    if identity != LinkDecision.NEW:
        return IdentityLaunchStatus.UNKNOWN
    if status == LaunchStatus.NEEDS_HUMAN:
        return IdentityLaunchStatus.NEEDS_HUMAN
    if status == LaunchStatus.ELIGIBLE_FOR_REVALIDATION:
        return IdentityLaunchStatus.ELIGIBLE_FOR_REVALIDATION
    return IdentityLaunchStatus.UNKNOWN
