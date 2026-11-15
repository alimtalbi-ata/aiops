"""Contract tests for the isolated, offline authorization reference policy."""
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from aiops2_server_authorization import AccessRequest, ServerGrant, authorize

NOW = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)
REQUEST = AccessRequest("alice", "tenant-a", "run-a", "core.run", "read")


def grant_for(request=REQUEST):
    return ServerGrant(request.subject_id, request.tenant_id, request.run_id,
                       request.resource, request.action, NOW + timedelta(minutes=5),
                       "policy-v1", "evidence-001")


def decide(request=REQUEST, grant=None, owner="tenant-a", now=NOW):
    return authorize(request, resolve_grant=lambda _: grant if grant is not None else grant_for(),
                     resolve_run_tenant=lambda _: owner, now=now)


def test_server_grant_positive_read_and_simulation_never_authorize_live():
    assert decide().allowed is True
    simulation = AccessRequest("alice", "tenant-a", "run-a", "demo.command", "simulate")
    result = decide(simulation, grant_for(simulation))
    assert result.allowed is True
    assert result.live_remediation_authorized is False
    assert result.evidence_id == "evidence-001"


def test_cross_tenant_and_actor_run_and_scope_mismatch_denied():
    for request in (
        replace(REQUEST, subject_id="bob"),
        replace(REQUEST, tenant_id="tenant-b"),
        replace(REQUEST, run_id="run-b"),
        replace(REQUEST, resource="twin.impact"),
        replace(REQUEST, action="simulate"),
    ):
        assert not decide(request, grant_for()).allowed
    assert not decide(owner="tenant-b").allowed


def test_expired_missing_malformed_and_live_actions_denied():
    assert not decide(grant=replace(grant_for(), expires_at=NOW)).allowed
    assert not decide(grant=replace(grant_for(), evidence_id="")).allowed
    assert not decide(grant=replace(grant_for(), policy_version="")).allowed
    assert not decide(grant=replace(grant_for(), expires_at=NOW.replace(tzinfo=None))).allowed
    assert not decide(now=NOW.replace(tzinfo=None)).allowed
    assert not decide(replace(REQUEST, action="execute_live")).allowed
    assert not decide(replace(REQUEST, subject_id="")).allowed
    assert not decide(owner="").allowed


def test_server_authority_failure_denied_without_live_authorization():
    def fail(_):
        raise TimeoutError("authority unavailable")
    for grant_resolver, owner_resolver in (
        (fail, lambda _: "tenant-a"),
        (lambda _: grant_for(), fail),
        (lambda _: None, lambda _: "tenant-a"),
    ):
        result = authorize(REQUEST, resolve_grant=grant_resolver,
                           resolve_run_tenant=owner_resolver, now=NOW)
        assert result.allowed is False
        assert result.live_remediation_authorized is False


def test_malformed_authority_payload_fails_closed_without_exception():
    for invalid in (
        replace(grant_for(), expires_at="not-a-datetime"),
        replace(grant_for(), expires_at=None),
        replace(grant_for(), policy_version=None),
        replace(grant_for(), evidence_id=123),
    ):
        result = decide(grant=invalid)
        assert result.allowed is False
        assert result.live_remediation_authorized is False
    assert decide(now=None).allowed is False


def test_offline_service_boundary_never_reads_upstream_on_denial():
    """Laboratory boundary: authorization precedes the protected Core/Twin read."""
    calls = []

    def protected_read(request, grant_resolver, owner_resolver):
        decision = authorize(request, resolve_grant=grant_resolver,
                             resolve_run_tenant=owner_resolver, now=NOW)
        if not decision.allowed:
            return {"state": "UNKNOWN", "reason": decision.reason,
                    "live_remediation_authorized": False}
        calls.append((request.tenant_id, request.run_id))
        return {"state": "SYNTHETIC", "run_id": request.run_id,
                "live_remediation_authorized": False}

    allowed = protected_read(REQUEST, lambda _: grant_for(), lambda _: "tenant-a")
    assert allowed["state"] == "SYNTHETIC"
    assert calls == [("tenant-a", "run-a")]

    for request, grant_resolver, owner_resolver in (
        (replace(REQUEST, tenant_id="tenant-b"), lambda _: grant_for(), lambda _: "tenant-a"),
        (REQUEST, lambda _: grant_for(), lambda _: "tenant-b"),
        (REQUEST, lambda _: None, lambda _: "tenant-a"),
        (REQUEST, lambda _: replace(grant_for(), expires_at=NOW), lambda _: "tenant-a"),
        (replace(REQUEST, action="execute_live"), lambda _: grant_for(), lambda _: "tenant-a"),
    ):
        denied = protected_read(request, grant_resolver, owner_resolver)
        assert denied["state"] == "UNKNOWN"
        assert denied["reason"] == "AUTHORIZATION_NOT_QUALIFIED"
        assert denied["live_remediation_authorized"] is False
        assert "run_id" not in denied
    assert calls == [("tenant-a", "run-a")], "denied requests must not reach upstream"


def test_run_ownership_not_queried_until_grant_is_valid():
    ownership_calls = []

    def owner(run_id):
        ownership_calls.append(run_id)
        return "tenant-a"

    for bad_grant in (
        None,
        replace(grant_for(), subject_id="other"),
        replace(grant_for(), expires_at=NOW),
        replace(grant_for(), evidence_id=""),
        replace(grant_for(), expires_at="invalid"),
    ):
        result = authorize(REQUEST, resolve_grant=lambda _, g=bad_grant: g,
                           resolve_run_tenant=owner, now=NOW)
        assert result.allowed is False
        assert ownership_calls == []

    result = authorize(REQUEST, resolve_grant=lambda _: grant_for(),
                       resolve_run_tenant=owner, now=NOW)
    assert result.allowed is True
    assert ownership_calls == ["run-a"]


def test_malformed_request_is_denied_before_any_resolver_call():
    calls = []

    def resolver(value):
        calls.append(value)
        raise AssertionError("must not be called")

    for request in (None, {}, "tenant-a", 123, replace(REQUEST, run_id=None)):
        decision = authorize(request, resolve_grant=resolver,
                             resolve_run_tenant=resolver, now=NOW)
        assert decision.allowed is False
        assert decision.live_remediation_authorized is False
    assert calls == []


def test_resource_action_matrix_denies_invalid_pairs_before_resolvers():
    calls = []

    def resolver(value):
        calls.append(value)
        raise AssertionError("invalid action must not reach authority or Run lookup")

    for resource, action in (
        ("core.run", "simulate"),
        ("twin.impact", "simulate"),
        ("copilot.context", "simulate"),
        ("demo.command", "read"),
        ("demo.command", "execute_live"),
        ("unknown.resource", "read"),
    ):
        request = replace(REQUEST, resource=resource, action=action)
        result = authorize(request, resolve_grant=resolver,
                           resolve_run_tenant=resolver, now=NOW)
        assert result.allowed is False
        assert result.live_remediation_authorized is False
    assert calls == []
