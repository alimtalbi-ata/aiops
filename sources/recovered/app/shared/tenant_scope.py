"""Shared conservative tenant-scope fence; no tenant ACL is established here.

Extracted from the signed NOC adapter's existing refusal contract. Any
tenant/organization/workspace/account claim requires a separate authenticated
tenant identity and server-side ACL, which this repository does not yet have.
"""
from __future__ import annotations

import re
import unicodedata

_TENANT_SCOPE_NAMES = frozenset({
    "tenant", "tenantid", "tenantname", "tenantkey", "tenantids",
    "org", "orgid", "orgname", "organization", "organizationid",
    "workspace", "workspaceid", "workspacename",
    "account", "accountid", "accountname",
    "customer", "customerid", "customername",
    "tenantaclqualified", "aclqualified",
    "orgref", "organizationref", "workspaceref",
    "accountref", "customerref",
})


def reject_unqualified_tenant_scope(value: object) -> None:
    """Reject nested and aliased scope claims, including null-valued claims."""
    pending = [value]
    visited = 0
    while pending:
        item = pending.pop()
        visited += 1
        if visited > 4096:
            raise ValueError("NOC tenant-scope scan bound exceeded")
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise ValueError("invalid tenant-scope key")
                normalized = re.sub(
                    r"[^a-z0-9]", "", unicodedata.normalize("NFKC", key).casefold()
                )
                if (normalized in _TENANT_SCOPE_NAMES
                        or normalized.startswith(("tenant", "organization", "workspace"))
                        or normalized.endswith((
                            "tenant", "tenantid", "orgid", "organizationid",
                            "workspaceid", "accountid", "customerid",
                        ))):
                    raise ValueError("tenant-scoped NOC source requires qualified ACL")
                pending.append(child)
        elif isinstance(item, list):
            pending.extend(item)
