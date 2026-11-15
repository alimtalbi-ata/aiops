"""Exercise the actual Portal authorization boundary with trusted lab resolvers."""
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.authorized_run_boundary import (
    ReadGrant, ReadScope, UnqualifiedReadPermission, read_authorized_run,
)

NOW = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)
SCOPE = ReadScope("actor-a", "tenant-a", "run-a")


def test_real_portal_boundary_positive_and_denied_paths():
    calls = []

    def grant(scope):
        calls.append("grant")
        return ReadGrant(scope.subject_id, scope.tenant_id, scope.run_id,
                         NOW + timedelta(minutes=1), "proof-a", "policy-v1", "core.run", "read")

    def owner(run_id):
        calls.append("owner")
        return {"run-a": "tenant-a", "run-b": "tenant-b"}.get(run_id)

    def read(tenant_id, run_id):
        calls.append("read")
        return {"tenant_id": tenant_id, "run_id": run_id,
                "state": "SYNTHETIC_SIMULATION_ONLY",
                "live_remediation_authorized": False}

    result = read_authorized_run(SCOPE, resolve_grant=grant,
                                 resolve_run_tenant=owner, read_run=read, now=NOW)
    assert result["run_id"] == "run-a"
    assert calls == ["grant", "owner", "read"]

    for scope in (replace(SCOPE, run_id="run-b"), replace(SCOPE, run_id="missing")):
        calls.clear()
        with pytest.raises(UnqualifiedReadPermission):
            read_authorized_run(scope, resolve_grant=grant,
                                resolve_run_tenant=owner, read_run=read, now=NOW)
        assert calls == ["grant", "owner"]

    calls.clear()
    with pytest.raises(UnqualifiedReadPermission):
        read_authorized_run(SCOPE,
                            resolve_grant=lambda _: replace(grant(SCOPE), expires_at=NOW),
                            resolve_run_tenant=owner, read_run=read, now=NOW)
    assert calls == ["grant"]


def test_real_portal_boundary_rejects_unqualified_upstream_payload():
    def grant(scope):
        return ReadGrant(scope.subject_id, scope.tenant_id, scope.run_id,
                         NOW + timedelta(minutes=1), "proof-a", "policy-v1", "core.run", "read")

    for payload in (
        {"run_id": "run-a", "tenant_id": "tenant-a",
         "state": "LIVE", "live_remediation_authorized": False},
        {"run_id": "run-a", "tenant_id": "tenant-b",
         "state": "SYNTHETIC_SIMULATION_ONLY", "live_remediation_authorized": False},
        {"run_id": "run-a", "tenant_id": "tenant-a",
         "state": "SYNTHETIC_SIMULATION_ONLY", "live_remediation_authorized": True},
        {"run_id": "run-a", "tenant_id": "tenant-a",
         "state": "SYNTHETIC_SIMULATION_ONLY", "live_remediation_authorized": False,
         "secret": "unqualified"},
    ):
        with pytest.raises(UnqualifiedReadPermission):
            read_authorized_run(SCOPE, resolve_grant=grant,
                                resolve_run_tenant=lambda _: "tenant-a",
                                read_run=lambda _tenant, _run, p=payload: p, now=NOW)


def test_resolver_failures_and_malformed_scope_never_reach_reader():
    calls = []

    def forbidden(*args):
        calls.append("unexpected")
        raise AssertionError("reader or resolver should not be called")

    for scope in (None, ReadScope("", "tenant-a", "run-a"),
                  ReadScope("actor-a", "", "run-a"),
                  ReadScope("actor-a", "tenant-a", "")):
        with pytest.raises(UnqualifiedReadPermission):
            read_authorized_run(scope, resolve_grant=forbidden,
                                resolve_run_tenant=forbidden,
                                read_run=forbidden, now=NOW)
    assert calls == []

    def unavailable(_):
        raise RuntimeError("authority unavailable")

    for grant_resolver in (lambda _: None, lambda _: object(), unavailable):
        with pytest.raises(UnqualifiedReadPermission):
            read_authorized_run(SCOPE, resolve_grant=grant_resolver,
                                resolve_run_tenant=forbidden,
                                read_run=forbidden, now=NOW)
    assert calls == []

    def valid(scope):
        return ReadGrant(scope.subject_id, scope.tenant_id, scope.run_id,
                         NOW + timedelta(minutes=1), "proof-a", "policy-v1", "core.run", "read")

    for owner_resolver in (lambda _: None, lambda _: "tenant-b", unavailable):
        with pytest.raises(UnqualifiedReadPermission):
            read_authorized_run(SCOPE, resolve_grant=valid,
                                resolve_run_tenant=owner_resolver,
                                read_run=forbidden, now=NOW)
    assert calls == []


def test_malformed_timezone_evidence_fails_closed_before_reader():
    from datetime import tzinfo

    class BrokenTimezone(tzinfo):
        def utcoffset(self, dt):
            raise ValueError("invalid timezone evidence")
        def dst(self, dt):
            return timedelta(0)

    calls = []
    def owner(_):
        calls.append("owner")
        return "tenant-a"
    def reader(*_):
        calls.append("reader")
        return {}
    def grant(scope):
        return ReadGrant(scope.subject_id, scope.tenant_id, scope.run_id,
                         datetime(2026, 11, 15, tzinfo=BrokenTimezone()), "proof-a",
                         "policy-v1", "core.run", "read")

    with pytest.raises(UnqualifiedReadPermission):
        read_authorized_run(SCOPE, resolve_grant=grant,
                            resolve_run_tenant=owner, read_run=reader, now=NOW)
    assert calls == []
    with pytest.raises(UnqualifiedReadPermission):
        read_authorized_run(SCOPE, resolve_grant=lambda _: None,
                            resolve_run_tenant=owner, read_run=reader,
                            now=datetime(2026, 11, 15, tzinfo=BrokenTimezone()))
    assert calls == []


def test_grant_for_other_resource_or_action_cannot_reach_owner_or_core():
    calls = []
    def forbidden(*args):
        calls.append("unexpected")
        raise AssertionError("cross-resource grant must not reach Core")
    for resource, action in (("demo.command", "simulate"),
                             ("twin.impact", "read"),
                             ("core.run", "simulate"),
                             ("core.run", "write")):
        def grant(scope):
            return ReadGrant(scope.subject_id, scope.tenant_id, scope.run_id,
                             NOW + timedelta(minutes=1), "proof-a", "policy-v1", resource, action)
        with pytest.raises(UnqualifiedReadPermission):
            read_authorized_run(SCOPE, resolve_grant=grant,
                                resolve_run_tenant=forbidden,
                                read_run=forbidden, now=NOW)
    assert calls == []


def test_missing_policy_version_rejected_before_run_lookup():
    calls = []
    def forbidden(*args):
        calls.append("unexpected")
        raise AssertionError("must not reach owner or Core")
    for version in ("", "   ", None):
        def grant(scope):
            return ReadGrant(scope.subject_id, scope.tenant_id, scope.run_id,
                             NOW + timedelta(minutes=1), "proof-a", version,
                             "core.run", "read")
        with pytest.raises(UnqualifiedReadPermission):
            read_authorized_run(SCOPE, resolve_grant=grant,
                                resolve_run_tenant=forbidden,
                                read_run=forbidden, now=NOW)
    assert calls == []
