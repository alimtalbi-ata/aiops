"""Offline regression: authoritative absence cannot be guessed."""
from dataclasses import replace

from app.core.fs147_immutable_link import Link
from app.core.fs147_authoritative_link import Admission, classify_authoritative_link


def sample():
    return Link("tenant", "key", "alert", "INC", "RUN", "EVID", "a" * 64, 147, "DEMO")


def test_cache_miss_is_unknown_until_authoritative_absence():
    x = sample()
    assert classify_authoritative_link(x) == Admission.UNKNOWN
    assert classify_authoritative_link(x, absence_verified=True) == Admission.NEW_CANDIDATE
    assert classify_authoritative_link(x, absence_verified=True, existing_verified=True) == Admission.UNKNOWN


def test_replay_requires_verified_existing_row():
    x = sample()
    assert classify_authoritative_link(x, x) == Admission.UNKNOWN
    assert classify_authoritative_link(x, x, existing_verified=True) == Admission.REPLAY
    assert classify_authoritative_link(x, x, existing_verified=True, absence_verified=True) == Admission.UNKNOWN
    assert classify_authoritative_link(replace(x, run_id="different"), x, existing_verified=True) == Admission.CONFLICT


def test_fail_closed_live_ticket_and_untrusted_flags():
    x = sample()
    assert classify_authoritative_link(replace(x, mode="LIVE"), absence_verified=True) == Admission.DENIED
    assert classify_authoritative_link(replace(x, glpi_ticket_id=146), absence_verified=True) == Admission.DENIED
    assert classify_authoritative_link(None, absence_verified=True) == Admission.UNKNOWN
    assert classify_authoritative_link(x, absence_verified=1) == Admission.UNKNOWN
    assert classify_authoritative_link(x, x, existing_verified=None) == Admission.UNKNOWN


def test_deterministic_replays_do_not_mutate():
    x = sample()
    for _ in range(20):
        assert classify_authoritative_link(x, x, existing_verified=True) == Admission.REPLAY
    assert x == sample()
