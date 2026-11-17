"""ACME Portal viewer authorization *decision contract*, offline only.

The module never authenticates a viewer or makes an allow decision by itself.
Only a trusted server-side identity provider can construct the authorization
evidence needed by a future adapter. No browser token or Core bearer accepted.
"""
from __future__ import annotations

import re
import hashlib
from dataclasses import dataclass

_ATTEMPT = re.compile(r"ACME-SIM-[A-F0-9]{16}\Z")
_RUN = re.compile(r"RUN-SIM-[A-F0-9]{24}\Z")
_ACTOR = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,95}\Z")
_TENANT = "ACME-TEST"


@dataclass(frozen=True)
class ViewerDecision:
    status: int
    reason: str

    @property
    def authorized(self) -> bool:
        return self.status == 200


def decide_viewer_access(*, authenticated_actor: object,
                         actor_tenants: object, requested_tenant: object,
                         requested_attempt: object, requested_run: object,
                         authorized_run_ids: object,
                         identity_authority_qualified: bool = False,
                         run_acl_authority_qualified: bool = False) -> ViewerDecision:
    """Pure policy over server-supplied claims; booleans are NOT attestation.

    The caller must independently establish both authorities; this contract
    alone is never an authentication or ACL enforcement boundary.
    """
    if (identity_authority_qualified is not True or run_acl_authority_qualified is not True):
        return ViewerDecision(503, "TENANT_ACL_NOT_QUALIFIED")
    if (type(authenticated_actor) is not str
            or not _ACTOR.fullmatch(authenticated_actor)):
        return ViewerDecision(401, "VIEWER_UNAUTHENTICATED")
    if (type(requested_tenant) is not str
            or type(requested_attempt) is not str
            or type(requested_run) is not str
            or requested_tenant != _TENANT
            or not _ATTEMPT.fullmatch(requested_attempt)
            or not _RUN.fullmatch(requested_run)):
        return ViewerDecision(404, "ACME_RESOURCE_NOT_FOUND")
    if (type(actor_tenants) not in (frozenset, set)
            or type(authorized_run_ids) not in (frozenset, set)
            or not all(type(x) is str for x in actor_tenants)
            or not all(type(x) is str for x in authorized_run_ids)):
        return ViewerDecision(503, "TENANT_ACL_NOT_QUALIFIED")
    # Even a fully matching allowlist must not authorize a mismatched attempt
    # and Run. Core's sandbox persists this deterministic mapping.
    canonical_run = "RUN-SIM-" + hashlib.sha256(
        (_TENANT + ":" + requested_attempt).encode("ascii")
    ).hexdigest()[:24].upper()
    if requested_run != canonical_run:
        return ViewerDecision(404, "ACME_RESOURCE_NOT_FOUND")
    if requested_tenant not in actor_tenants:
        return ViewerDecision(403, "VIEWER_TENANT_DENIED")
    if requested_run not in authorized_run_ids:
        return ViewerDecision(404, "ACME_RESOURCE_NOT_FOUND")
    # This is a conditional policy result, not a proof that the claims are
    # server-derived or backed by an authenticated Core readback. An adapter
    # must verify the mapping against Core before any evidence disclosure.
    return ViewerDecision(200, "POLICY_CONDITIONS_SATISFIED_ONLY")
