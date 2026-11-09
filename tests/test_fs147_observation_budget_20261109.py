"""Negative admission tests for bounded fs-lab read-only observations."""
from datetime import datetime, timezone
from worker.fs147_observation_gate import admit_observation

NOW = datetime(2026, 11, 9, 4, 20, tzinfo=timezone.utc)


def envelope(evidence):
    return {
        "tenant_id": "tenant-demo", "ticket_id": 147, "run_id": "run-demo",
        "source": "fs-lab", "access_mode": "read-only",
        "provenance_verified": True, "source_event_id": "event-1",
        "observed_at": "2026-11-09T04:19:00Z",
        "received_at": "2026-11-09T04:19:10Z", "evidence": evidence,
    }


def admit(evidence):
    return admit_observation(envelope(evidence), now=NOW,
                             expected_run_id="run-demo",
                             expected_tenant_id="tenant-demo",
                             expected_ticket_id=147)


def test_small_observation_still_accepted():
    assert admit({"availability": True})["status"] == "ACCEPTED"


def test_oversized_string_fails_closed():
    result = admit({"log": "x" * 4097})
    assert result["status"] == "UNKNOWN"
    assert result["fingerprint"] is None


def test_excessive_node_count_fails_closed():
    result = admit({"samples": [1] * 1025})
    assert result["status"] == "UNKNOWN"
    assert result["fingerprint"] is None


def test_oversized_utf8_payload_fails_closed():
    result = admit({"a": "é" * 4096, "b": "é" * 4096,
                    "c": "é" * 4096, "d": "é" * 4096,
                    "e": "é" * 4096, "f": "é" * 4096,
                    "g": "é" * 4096, "h": "é" * 4096})
    assert result["status"] == "UNKNOWN"
    assert result["reason"] == "EVIDENCE_TOO_LARGE"
