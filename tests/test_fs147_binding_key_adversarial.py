"""FS147 adversarial key invariants; pure offline tests, no service calls."""
import itertools

import pytest

from app.core.fs147_binding_key import KeyStatus, derive_fs147_key

FIELDS = ("tenant_id", "alert_fingerprint", "incident_id", "run_id", "evidence_id")
BASE = dict(tenant_id="tenant-a", alert_fingerprint="alert-a",
            incident_id="incident-a", run_id="run-a", evidence_id="evidence-a",
            ticket_id=147, mode="DEMO")


def key(**updates):
    return derive_fs147_key(**(BASE | updates))


@pytest.mark.parametrize("left,right", list(itertools.combinations(FIELDS, 2)))
def test_cross_field_swap_never_aliases(left, right):
    swapped = BASE.copy()
    swapped[left], swapped[right] = swapped[right], swapped[left]
    assert key().status is KeyStatus.READY
    assert key(**swapped).status is KeyStatus.READY
    assert key().key != key(**swapped).key


@pytest.mark.parametrize("unsafe", [
    "e\u0301",  # NFD; do not normalize silently
    "\u202eabc",  # bidi override
    "abc\u2066",  # bidi isolate
    "abc\x00",  # NUL
    "abc\ud800",  # unpaired surrogate
    " x", "x ", "", "x" * 513,
])
@pytest.mark.parametrize("field", FIELDS)
def test_unsafe_identifiers_never_produce_key(field, unsafe):
    result = key(**{field: unsafe})
    assert result.status is KeyStatus.UNKNOWN
    assert result.key is None


@pytest.mark.parametrize("mode,ticket", [
    ("LIVE", 147), ("LIVE", 146), ("LIVE", None),
    ("DEMO", 146), ("DEMO", 148),
])
def test_explicit_denial_precedes_missing_correlation(mode, ticket):
    result = key(mode=mode, ticket_id=ticket, evidence_id=None)
    assert result.status is KeyStatus.DENIED
    assert result.key is None


def test_unknown_mode_never_yields_ready_even_with_complete_identity():
    for mode in (None, "", "demo", "UNKNOWN", True, 1):
        result = key(mode=mode)
        assert result.status is KeyStatus.UNKNOWN
        assert result.key is None
