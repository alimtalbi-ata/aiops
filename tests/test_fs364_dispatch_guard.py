"""Offline, side-effect-free dispatch revocation tests."""
import unittest
from dataclasses import replace
from app.core.fs364_dispatch_guard import DispatchState, dispatch_still_admissible


def valid():
    return DispatchState(
        tenant_id="tenant-A", run_id="RUN-4FABD1786F107E51",
        mode="DEMO", ticket_id=147, state="WAITING_HUMAN",
        state_version="v1", policy_decision="ALLOW", policy_version="p1",
        stop_auto=False, human_answer_verified=True,
        approval_specific=True, approval_valid=True, glpi_verified=True,
        authenticated=True, acl_ok=True,
    )


class DispatchGuardTests(unittest.TestCase):
    def test_unchanged_demo_snapshot_is_only_candidate(self):
        s = valid()
        self.assertTrue(dispatch_still_admissible(s, s))

    def test_revocations_after_admission_fail_closed(self):
        s = valid()
        for changes in (
            {"policy_decision": "DENY"}, {"policy_version": "p2"},
            {"state_version": "v2"}, {"state": "BLOCKED_NO_EFFECT"},
            {"stop_auto": True}, {"approval_valid": False},
            {"approval_specific": False}, {"human_answer_verified": False},
            {"glpi_verified": False}, {"authenticated": False},
            {"acl_ok": False}, {"ticket_id": 146}, {"mode": "LIVE"},
            {"tenant_id": "tenant-B"}, {"run_id": "RUN-other"},
        ):
            with self.subTest(changes=changes):
                self.assertFalse(dispatch_still_admissible(s, replace(s, **changes)))

    def test_invalid_original_or_missing_versions_rejected(self):
        s = valid()
        self.assertFalse(dispatch_still_admissible(replace(s, mode="LIVE"), s))
        self.assertFalse(dispatch_still_admissible(replace(s, ticket_id=146), s))
        self.assertFalse(dispatch_still_admissible(s, replace(s, policy_version="")))
        self.assertFalse(dispatch_still_admissible(s, None))
        self.assertFalse(dispatch_still_admissible(None, s))
        self.assertFalse(dispatch_still_admissible(s, replace(s, stop_auto=None)))


if __name__ == "__main__":
    unittest.main()
