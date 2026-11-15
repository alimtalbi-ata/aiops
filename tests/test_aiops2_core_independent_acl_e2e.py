"""Offline E2E: Portal authorization never substitutes for source-side ACL."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.authorized_run_boundary import (
    ReadGrant, UnqualifiedReadPermission, read_authorized_run,
)
from portal.core_synthetic_read_gate import read_core_synthetic_run
from portal.server_identity_scope import (
    EXPECTED_AUDIENCE, VerifiedPrincipal, resolve_server_read_scope,
)

NOW = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)


def test_portal_allow_cannot_override_independent_core_deny():
    calls = []
    scope = resolve_server_read_scope(
        "run-a",
        resolve_verified_principal=lambda: VerifiedPrincipal(
            "actor-a", "tenant-a", EXPECTED_AUDIENCE, "identity-evidence"))

    def grant(scope):
        return ReadGrant(scope.subject_id, scope.tenant_id, scope.run_id,
                         NOW + timedelta(minutes=1), "grant-evidence",
                         "policy-v1", "core.run", "read")

    def source(tenant, run):
        calls.append("storage")
        return {"run_id": run, "tenant_id": tenant,
                "state": "SYNTHETIC_SIMULATION_ONLY",
                "live_remediation_authorized": False}

    def portal_read(_tenant, _run):
        calls.append("core-gate")
        return read_core_synthetic_run(
            scope, resolve_core_grant=lambda _: None,
            resolve_core_owner=lambda _: "tenant-a",
            load_core_synthetic_run=source, now=NOW)

    with pytest.raises(UnqualifiedReadPermission):
        read_authorized_run(
            scope, resolve_grant=grant,
            resolve_run_tenant=lambda _: "tenant-a",
            read_run=portal_read, now=NOW)
    assert calls == ["core-gate"]
    assert "storage" not in calls


def test_portal_and_core_both_authorize_before_synthetic_storage():
    calls = []
    scope = resolve_server_read_scope(
        "run-a",
        resolve_verified_principal=lambda: VerifiedPrincipal(
            "actor-a", "tenant-a", EXPECTED_AUDIENCE, "identity-evidence"))

    def grant(scope):
        return ReadGrant(scope.subject_id, scope.tenant_id, scope.run_id,
                         NOW + timedelta(minutes=1), "grant-evidence",
                         "policy-v1", "core.run", "read")

    def owner(run):
        calls.append("owner")
        return "tenant-a"

    def storage(tenant, run):
        calls.append("storage")
        return {"run_id": run, "tenant_id": tenant,
                "state": "SYNTHETIC_SIMULATION_ONLY",
                "live_remediation_authorized": False}

    def core(tenant, run):
        calls.append("core-gate")
        return read_core_synthetic_run(
            scope, resolve_core_grant=grant, resolve_core_owner=owner,
            load_core_synthetic_run=storage, now=NOW)

    result = read_authorized_run(
        scope, resolve_grant=grant, resolve_run_tenant=owner,
        read_run=core, now=NOW)
    assert result["live_remediation_authorized"] is False
    assert calls == ["owner", "core-gate", "owner", "storage"]

    calls.clear()
    with pytest.raises(UnqualifiedReadPermission):
        read_core_synthetic_run(
            scope, resolve_core_grant=grant,
            resolve_core_owner=lambda _: "tenant-b",
            load_core_synthetic_run=storage, now=NOW)
    assert calls == []
