"""Offline contract tests: never call GLPI, Temporal or production."""
from dataclasses import replace
import pytest

from app.core.fs147_binding_key import derive_fs147_key, KeyStatus

BASE = dict(
    tenant_id="tenant-a", alert_fingerprint="prometheus:fs-lab",
    incident_id="incident-147", run_id="run-147",
    evidence_id="evidence-147", ticket_id=147, mode="DEMO",
)


def derive(**changes):
    return derive_fs147_key(**(BASE | changes))


def test_stable_replay_and_no_mutation():
    before = BASE.copy()
    first = derive()
    assert first.status is KeyStatus.READY
    assert first.key.startswith("fs147:v1:")
    assert first == derive()
    assert BASE == before


@pytest.mark.parametrize("field", [
    "tenant_id", "alert_fingerprint", "incident_id", "run_id", "evidence_id",
])
def test_distinct_binding_distinct_key(field):
    assert derive(**{field: BASE[field] + "-different"}).key != derive().key


@pytest.mark.parametrize("field", [
    "tenant_id", "alert_fingerprint", "incident_id", "run_id", "evidence_id",
])
@pytest.mark.parametrize("bad", [None, "", " ", "x\u200b", "x\n", 123, True])
def test_missing_or_unsafe_identity_unknown(field, bad):
    result = derive(**{field: bad})
    assert result.status is KeyStatus.UNKNOWN
    assert result.key is None


@pytest.mark.parametrize("change,status", [
    ({"mode": "LIVE"}, KeyStatus.DENIED),
    ({"mode": None}, KeyStatus.UNKNOWN),
    ({"mode": "demo"}, KeyStatus.UNKNOWN),
    ({"ticket_id": 146}, KeyStatus.DENIED),
    ({"ticket_id": 148}, KeyStatus.DENIED),
    ({"ticket_id": None}, KeyStatus.UNKNOWN),
    ({"ticket_id": True}, KeyStatus.UNKNOWN),
    ({"ticket_id": "147"}, KeyStatus.UNKNOWN),
])
def test_mode_and_ticket_fail_closed(change, status):
    result = derive(**change)
    assert result.status is status
    assert result.key is None


def test_tuple_boundaries_not_ambiguous():
    a = derive(tenant_id="ab", alert_fingerprint="c")
    b = derive(tenant_id="a", alert_fingerprint="bc")
    assert a.status is b.status is KeyStatus.READY
    assert a.key != b.key
