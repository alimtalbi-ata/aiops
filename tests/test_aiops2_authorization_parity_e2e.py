"""Offline parity E2E: reference policy and actual Portal boundary must agree.

No HTTP production route, external authority, or live Core access.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "app"))

from aiops2_server_authorization import AccessRequest, ServerGrant, authorize
from portal.authorized_run_boundary import (
    ReadGrant, ReadScope, UnqualifiedReadPermission, read_authorized_run,
)

NOW = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)
SCOPE = ReadScope("actor-a", "tenant-a", "run-a")
REQUEST = AccessRequest("actor-a", "tenant-a", "run-a", "core.run", "read")


def test_cross_policy_same_scope_freshness_and_tenant_authority():
    """A reference ALLOW and Portal read must agree; DENY never reads Core."""
    for remaining, owner, resource, action, expected in (
        (timedelta(minutes=1), "tenant-a", "core.run", "read", True),
        (timedelta(minutes=5), "tenant-a", "core.run", "read", True),
        (timedelta(0), "tenant-a", "core.run", "read", False),
        (timedelta(minutes=5, microseconds=1), "tenant-a", "core.run", "read", False),
        (timedelta(minutes=1), "tenant-b", "core.run", "read", False),
        (timedelta(minutes=1), "tenant-a", "demo.command", "simulate", False),
    ):
        calls = []
        def resolve_owner(run_id):
            calls.append("owner")
            return owner
        def core_reader(tenant_id, run_id):
            calls.append("core")
            return {"run_id": run_id, "tenant_id": tenant_id,
                    "state": "SYNTHETIC_SIMULATION_ONLY",
                    "live_remediation_authorized": False}
        def reference_grant(_):
            return ServerGrant(SCOPE.subject_id, SCOPE.tenant_id, SCOPE.run_id,
                               resource, action, NOW + remaining,
                               "policy-v1", "proof-a")
        def portal_grant(_):
            return ReadGrant(SCOPE.subject_id, SCOPE.tenant_id, SCOPE.run_id,
                             NOW + remaining, "proof-a", "policy-v1",
                             resource, action)

        # Compare exact Core-read authority: a DEMO grant is never a Core grant.
        decision = authorize(REQUEST, resolve_grant=reference_grant,
                             resolve_run_tenant=resolve_owner, now=NOW)
        assert decision.allowed is expected
        calls.clear()
        try:
            result = read_authorized_run(
                SCOPE, resolve_grant=portal_grant,
                resolve_run_tenant=resolve_owner, read_run=core_reader, now=NOW)
        except UnqualifiedReadPermission:
            portal_allowed = False
        else:
            portal_allowed = True
            assert result["live_remediation_authorized"] is False
        assert portal_allowed is expected
        assert ("core" in calls) is expected
        if not expected:
            assert "core" not in calls
