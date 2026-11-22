"""Dormant Core-side exact-Run synthetic read gate.

This is NOT a production Core endpoint. The source service must independently
enforce tenant/Run authority; a Portal decision or shared bearer is insufficient.
Only trusted server-side resolvers are admissible.
"""
from datetime import datetime
from typing import Callable, Optional

from portal.authorized_run_boundary import (
    ReadGrant, ReadScope, UnqualifiedReadPermission, read_authorized_run,
)


def read_core_synthetic_run(
    scope: ReadScope,
    *,
    resolve_core_grant: Callable[[ReadScope], Optional[ReadGrant]],
    resolve_core_owner: Callable[[str], Optional[str]],
    load_core_synthetic_run: Callable[[str, str], dict],
    now: datetime,
) -> dict:
    """Reauthorize at the source, independent of the Portal ACL.

    No real Core API, datastore or live remediation is accessed here.
    """
    return read_authorized_run(
        scope,
        resolve_grant=resolve_core_grant,
        resolve_run_tenant=resolve_core_owner,
        read_run=load_core_synthetic_run,
        now=now,
    )
