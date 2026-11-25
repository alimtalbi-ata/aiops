"""Experimental in-memory tenant read contract. Not production authentication."""
from dataclasses import dataclass
from hashlib import sha256
from hmac import compare_digest

@dataclass(frozen=True)
class Grant:
    actor: str
    tenant: str
    permissions: frozenset[str]

class TenantReadModel:
    def __init__(self, grants, incidents, evidence):
        # Server-provisioned token digests and tenant-bound records only.
        self.grants = dict(grants)
        self.incidents = dict(incidents)
        self.evidence = dict(evidence)

    def read(self, token, incident_id):
        if not isinstance(token, str) or not token or len(token) > 4096:
            raise PermissionError("UNAUTHORIZED")
        digest = sha256(token.encode()).hexdigest()
        grant = next((g for d, g in self.grants.items()
                      if compare_digest(d, digest)), None)
        if grant is None or not grant.actor or not grant.tenant or "incident:read" not in grant.permissions:
            raise PermissionError("UNAUTHORIZED")
        key = (grant.tenant, incident_id)
        if key not in self.incidents:
            raise LookupError("NOT_FOUND")
        incident = self.incidents[key]
        proof = self.evidence.get(key, ())
        return {"tenant": grant.tenant, "incident_id": incident_id,
                "service": incident["service"],
                "evidence_ids": list(proof),
                "rca": "UNKNOWN",
                "classification": "EXPERIMENTAL_SYNTHETIC",
                "live_remediation_authorized": False}
