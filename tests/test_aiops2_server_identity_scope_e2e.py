"""Offline integration of trusted server identity scope and actual Portal ACL."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.server_identity_scope import (
    EXPECTED_AUDIENCE, VerifiedPrincipal, resolve_server_read_scope,
)
from portal.authorized_run_boundary import (
    ReadGrant, UnqualifiedReadPermission, read_authorized_run,
)

NOW = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)


def test_trusted_identity_scope_to_exact_run_core_read():
    calls = []
    principal = VerifiedPrincipal("actor-a", "tenant-a", EXPECTED_AUDIENCE, "identity-proof")

    def identity():
        calls.append("identity")
        return principal

    def grant(scope):
        calls.append("grant")
        return ReadGrant(scope.subject_id, scope.tenant_id, scope.run_id,
                         NOW + timedelta(minutes=1), "grant-proof", "policy-v1",
                         "core.run", "read")

    def owner(run_id):
        calls.append("owner")
        return {"run-a": "tenant-a", "run-b": "tenant-b"}.get(run_id)

    def core(tenant, run):
        calls.append("core")
        return {"tenant_id": tenant, "run_id": run,
                "state": "SYNTHETIC_SIMULATION_ONLY",
                "live_remediation_authorized": False}

    scope = resolve_server_read_scope("run-a", resolve_verified_principal=identity)
    result = read_authorized_run(scope, resolve_grant=grant,
                                 resolve_run_tenant=owner, read_run=core, now=NOW)
    assert result["run_id"] == "run-a"
    assert calls == ["identity", "grant", "owner", "core"]

    calls.clear()
    scope = resolve_server_read_scope("run-b", resolve_verified_principal=identity)
    with pytest.raises(UnqualifiedReadPermission):
        read_authorized_run(scope, resolve_grant=grant,
                            resolve_run_tenant=owner, read_run=core, now=NOW)
    assert calls == ["identity", "grant", "owner"]


def test_invalid_identity_never_reaches_grant_or_core():
    calls = []
    def forbidden(*args):
        calls.append("unexpected")
        raise AssertionError("must not reach ACL or Core")

    for principal in (
        None,
        object(),
        VerifiedPrincipal("actor-a", "tenant-a", "wrong-audience", "proof"),
        VerifiedPrincipal("", "tenant-a", EXPECTED_AUDIENCE, "proof"),
        VerifiedPrincipal("actor-a", "", EXPECTED_AUDIENCE, "proof"),
        VerifiedPrincipal("actor-a", "tenant-a", EXPECTED_AUDIENCE, ""),
    ):
        with pytest.raises(UnqualifiedReadPermission):
            resolve_server_read_scope(
                "run-a", resolve_verified_principal=lambda p=principal: p)
    with pytest.raises(UnqualifiedReadPermission):
        resolve_server_read_scope("run-a", resolve_verified_principal=forbidden)
    assert calls == ["unexpected"]
