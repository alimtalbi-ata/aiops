"""Synthetic atomic Twin/Evidence snapshot gate (ADR-003 candidate).

The adapter MUST provide both rows from ONE database snapshot/transaction.
A matching string alone is not proof of transactionality or authenticity.
Production backend ACL and attestation remain separate requirements.
"""
from dataclasses import dataclass
from resource_binding import Resource, ScopedFixtureBackend, _scope, _identifier, _digest, policy_evaluate


@dataclass(frozen=True)
class SnapshotPair:
    snapshot_id: str
    twin: Resource
    evidence: Resource


def snapshot_pair_decision(*, event, assertion, verifier, fetch_pair):
    """Deny-first synthetic oracle; never authorizes mutation."""
    if not isinstance(event, dict):
        return "DENY"
    try:
        tenant, instance = event["tenant"], event["instance"]
        _scope(tenant)
        _scope(instance)
        _identifier(event["event"])
        _digest(event["digest"])
        _identifier(event["twin_identifier"])
        _identifier(event["evidence_identifier"])
        _identifier(event["snapshot_id"])
        principal = verifier.verify(assertion)
        if (principal.tenant != tenant or principal.instance != instance or
                not {"twin:read", "evidence:read"}.issubset(principal.permissions)):
            return "DENY"
        # Exactly ONE backend call; adapter contract requires transactionally
        # consistent pair, not two independently timed fetches.
        pair = fetch_pair(tenant=tenant, instance=instance,
                          twin_identifier=event["twin_identifier"],
                          evidence_identifier=event["evidence_identifier"],
                          snapshot_id=event["snapshot_id"])
        if not isinstance(pair, SnapshotPair) or pair.snapshot_id != event["snapshot_id"]:
            return "DENY"
        _identifier(pair.snapshot_id)
        for row, kind, identifier in (
            (pair.twin, "twin", event["twin_identifier"]),
            (pair.evidence, "evidence", event["evidence_identifier"]),
        ):
            ScopedFixtureBackend._validate(row)
            if (row.resource, row.tenant, row.instance, row.identifier) != (
                    kind, tenant, instance, identifier):
                return "DENY"
        return policy_evaluate(event=event, twin=pair.twin, evidence=pair.evidence)
    except (PermissionError, KeyError, TypeError, ValueError, AttributeError):
        return "DENY"
