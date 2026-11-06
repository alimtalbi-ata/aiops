"""FS364 regression: stale or malformed admission cannot authorize dispatch."""
from dataclasses import replace
from app.core.fs364_dispatch_guard import DispatchState, dispatch_still_admissible


def admissible():
    return DispatchState(
        tenant_id="tenant-demo", run_id="RUN-4FABD1786F107E51",
        mode="DEMO", ticket_id=147, state="WAITING_HUMAN",
        state_version="v1", policy_decision="ALLOW", policy_version="p1",
        stop_auto=False, human_answer_verified=True,
        approval_specific=True, approval_valid=True, glpi_verified=True,
        authenticated=True, acl_ok=True,
    )


def test_identical_valid_snapshots_are_only_predicate_admissible():
    state = admissible()
    assert dispatch_still_admissible(state, state)


def test_admission_must_itself_have_passed_all_gates():
    good = admissible()
    for field, value in (
        ("stop_auto", True),
        ("human_answer_verified", False),
        ("approval_specific", False),
        ("approval_valid", False),
        ("glpi_verified", False),
        ("authenticated", False),
        ("acl_ok", False),
        ("policy_decision", "DENY"),
        ("state", "BLOCKED_NO_EFFECT"),
    ):
        assert not dispatch_still_admissible(replace(good, **{field: value}), good), field


def test_malformed_admission_boolean_is_rejected():
    good = admissible()
    assert not dispatch_still_admissible(replace(good, approval_valid=1), good)
    assert not dispatch_still_admissible(good, replace(good, approval_valid=1))


def test_live_and_wrong_ticket_never_admit():
    good = admissible()
    for field, value in (("mode", "LIVE"), ("ticket_id", 146)):
        bad = replace(good, **{field: value})
        assert not dispatch_still_admissible(bad, bad)
        assert not dispatch_still_admissible(bad, good)
