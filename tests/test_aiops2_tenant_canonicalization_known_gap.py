"""Offline tenant-identity trust-boundary contract for #713.

The canonicalization decision belongs to Core/identity. No network, secrets or LIVE.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from aiops2_event_correlation import InvalidEvent, correlate_events, normalize_event

AS_OF = "2026-11-15T12:00:00Z"


def receipt(tenant_id, source_event_id):
    return {
        "tenant_id": tenant_id,
        "source": "checkmk",
        "source_event_id": source_event_id,
        "ci_id": "san-01",
        "service_id": "payments",
        "severity": "P1",
        "evidence_sha256": "a" * 64,
        "observed_at": "2026-11-15T11:59:00Z",
        "known_at": "2026-11-15T11:59:05Z",
    }


@pytest.mark.parametrize("tenant", [" acme", "acme ", " acme ", "acme\t"])
@pytest.mark.xfail(
    strict=True,
    raises=InvalidEvent,
    reason="KNOWN GAP #713: Core has not agreed canonical tenant identity; whitespace is accepted",
)
def test_noncanonical_tenant_identity_must_be_rejected_at_boundary(tenant):
    # Intentionally records the desired fail-closed contract as an expected failure.
    # Remove xfail only after Core agrees a canonical identity rule and code is fixed.
    normalize_event(receipt(tenant, "san-1"))


def test_untrusted_whitespace_variant_never_grants_live_authority():
    result = correlate_events(
        [receipt("acme", "san-1"), receipt(" acme ", "san-2")],
        as_of=AS_OF,
    )
    assert result["runtime_attested"] is False
    assert result["live_remediation_authorized"] is False
    assert all(i["impact_state"] == "UNKNOWN" for i in result["incidents"])
    assert all(i["live_remediation_authorized"] is False for i in result["incidents"])
    # Current observed implementation splits the tenant namespace. This is NOT
    # a desired identity contract and must not be interpreted as isolation proof.
    assert len(result["incidents"]) == 2
