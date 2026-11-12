"""Candidate-only action-bound HITL guard contract; never dispatches live actions."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import unittest

@dataclass(frozen=True)
class Intent:
    tenant_id: str
    ticket_id: int
    run_id: str
    action_id: str
    target: str
    parameters_digest: str
    policy_revision: str
    expires_at: datetime
    dry_run: bool = True

def digest(intent):
    fields = (intent.tenant_id, intent.ticket_id, intent.run_id, intent.action_id,
              intent.target, intent.parameters_digest, intent.policy_revision,
              intent.expires_at.isoformat(), intent.dry_run)
    return hashlib.sha256(json.dumps(fields, separators=(',', ':')).encode()).hexdigest()

def guard(intent, approval, *, now, critic_pass, policy_pass, evidence_fresh,
          claim_result, temporal_run_id):
    """Decision only; UNKNOWN and BLOCKED are never action authorization."""
    # Reject malformed or empty action bindings before considering an approval.
    bound = (intent.tenant_id, intent.run_id, intent.action_id, intent.target,
             intent.parameters_digest, intent.policy_revision, temporal_run_id)
    if any(not isinstance(v, str) or not v.strip() for v in bound):
        return 'UNKNOWN'
    if type(intent.ticket_id) is not int or intent.ticket_id <= 0:
        return 'UNKNOWN'
    if claim_result is not True:
        return 'UNKNOWN' if claim_result is None or claim_result is not False else 'DUPLICATE_RUN'
    if not (critic_pass is True and policy_pass is True and evidence_fresh is True):
        return 'BLOCKED'
    if any(not isinstance(t, datetime) or t.tzinfo is None or t.utcoffset() is None
           for t in (now, intent.expires_at)):
        return 'UNKNOWN'
    if now >= intent.expires_at or temporal_run_id != intent.run_id:
        return 'BLOCKED'
    if not isinstance(approval, dict):
        return 'UNKNOWN'
    required = {'tenant_id': intent.tenant_id, 'ticket_id': intent.ticket_id,
                'run_id': intent.run_id, 'action_id': intent.action_id,
                'action_digest': digest(intent), 'policy_revision': intent.policy_revision}
    # Python considers True == 1: never accept boolean ticket IDs as approvals.
    if type(approval.get('ticket_id')) is not int:
        return 'BLOCKED'
    if any(approval.get(k) != v for k, v in required.items()):
        return 'BLOCKED'
    requester = approval.get('requester_id')
    approver = approval.get('approver_id')
    if (approval.get('decision') != 'APPROVED'
            or not isinstance(requester, str) or not requester.strip()
            or not isinstance(approver, str) or not approver.strip()
            or requester.strip() == approver.strip()):
        return 'BLOCKED'
    deadline = approval.get('valid_until')
    if not isinstance(deadline, datetime) or deadline.tzinfo is None or deadline.utcoffset() is None:
        return 'UNKNOWN'
    if now >= deadline:
        return 'BLOCKED'
    return 'SIMULATE' if intent.dry_run is True else 'BLOCKED'

class ActionBindingTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 8, tzinfo=timezone.utc)
        self.intent = Intent('tenant-demo', 147, 'RUN-FS147-A', 'ACT-INSPECT',
                             '/fs-lab', 'sha256:read-only', 'policy-v1',
                             self.now + timedelta(minutes=5))
        self.approval = dict(tenant_id='tenant-demo', ticket_id=147,
                             run_id='RUN-FS147-A', action_id='ACT-INSPECT',
                             action_digest=digest(self.intent), policy_revision='policy-v1',
                             decision='APPROVED', requester_id='requester',
                             approver_id='reviewer', valid_until=self.now + timedelta(minutes=2))
        self.kw = dict(now=self.now, critic_pass=True, policy_pass=True,
                       evidence_fresh=True, claim_result=True, temporal_run_id='RUN-FS147-A')

    def check(self, approval=None, intent=None, **overrides):
        return guard(intent or self.intent, self.approval if approval is None else approval,
                     **(self.kw | overrides))

    def test_simulated_only(self):
        self.assertEqual(self.check(), 'SIMULATE')
        self.assertEqual(self.check(intent=Intent(**(self.intent.__dict__ | {'dry_run': False}))), 'BLOCKED')

    def test_dry_run_must_be_literal_boolean_true(self):
        for value in (False, None, 1, 0, 'true', 'false', 'yes', [], {}):
            with self.subTest(value=value):
                altered = Intent(**(self.intent.__dict__ | {'dry_run': value}))
                approval = self.approval | {'action_digest': digest(altered)}
                self.assertEqual(self.check(intent=altered, approval=approval), 'BLOCKED')

    def test_binding_rejections(self):
        for key, value in [('ticket_id', 146), ('run_id', 'RUN-OTHER'),
                           ('tenant_id', 'other'), ('action_id', 'DELETE'),
                           ('action_digest', 'sha256:wrong'), ('policy_revision', 'old'),
                           ('decision', 'DENIED'), ('approver_id', 'requester')]:
            with self.subTest(key=key):
                self.assertEqual(self.check(approval=self.approval | {key: value}), 'BLOCKED')

    def test_approval_ticket_boolean_never_matches_integer_one(self):
        intent = Intent(**(self.intent.__dict__ | {'ticket_id': 1}))
        approval = self.approval | {'ticket_id': True, 'action_digest': digest(intent)}
        self.assertEqual(self.check(intent=intent, approval=approval), 'BLOCKED')
        approval = approval | {'ticket_id': 1}
        self.assertEqual(self.check(intent=intent, approval=approval), 'SIMULATE')

    def test_approver_identity_must_be_nonempty_distinct_string(self):
        for key, value in [('requester_id', None), ('requester_id', ''),
                           ('requester_id', '  '), ('requester_id', 1),
                           ('approver_id', 0), ('approver_id', False),
                           ('approver_id', []), ('approver_id', '  '),
                           ('approver_id', ' requester ')]:
            with self.subTest(key=key, value=value):
                self.assertEqual(self.check(approval=self.approval | {key: value}), 'BLOCKED')

    def test_malformed_action_binding_fails_closed(self):
        for key, value in [('tenant_id', ''), ('tenant_id', '  '),
                           ('run_id', None), ('action_id', 0),
                           ('target', ''), ('parameters_digest', []),
                           ('policy_revision', ' '), ('ticket_id', True),
                           ('ticket_id', 0)]:
            with self.subTest(key=key, value=value):
                altered = Intent(**(self.intent.__dict__ | {key: value}))
                self.assertEqual(self.check(intent=altered), 'UNKNOWN')
        self.assertEqual(self.check(temporal_run_id=''), 'UNKNOWN')

    def test_expiration_and_temporal_mismatch(self):
        self.assertEqual(self.check(now=self.intent.expires_at), 'BLOCKED')
        self.assertEqual(self.check(temporal_run_id='RUN-OTHER'), 'BLOCKED')
        self.assertEqual(self.check(approval=self.approval | {'valid_until': self.now}), 'BLOCKED')

    def test_fail_closed_decisions(self):
        for key in ('critic_pass', 'policy_pass', 'evidence_fresh'):
            with self.subTest(key=key):
                self.assertEqual(self.check(**{key: False}), 'BLOCKED')
        self.assertEqual(self.check(approval={}), 'BLOCKED')
        self.assertEqual(self.check(approval='unavailable'), 'UNKNOWN')

    def test_claim_and_replay(self):
        self.assertEqual(self.check(claim_result=False), 'DUPLICATE_RUN')
        for ambiguous in (None, 1, 0, 'ok'):
            with self.subTest(ambiguous=ambiguous):
                self.assertEqual(self.check(claim_result=ambiguous), 'UNKNOWN')
        self.assertEqual(self.check(claim_result=False), 'DUPLICATE_RUN')

    def test_untrusted_clock_and_expiry_fail_closed(self):
        naive = self.now.replace(tzinfo=None)
        self.assertEqual(self.check(now=naive), 'UNKNOWN')
        self.assertEqual(self.check(approval=self.approval | {'valid_until': naive}), 'UNKNOWN')
        self.assertEqual(self.check(approval=self.approval | {'valid_until': '2026-11-08T00:02:00Z'}), 'UNKNOWN')
        altered = Intent(**(self.intent.__dict__ | {'expires_at': naive}))
        self.assertEqual(self.check(intent=altered), 'UNKNOWN')

    def test_digest_changes_with_bound_fields(self):
        for key, value in [('ticket_id', 146), ('run_id', 'other'),
                           ('target', '/tmp'), ('parameters_digest', 'other'),
                           ('policy_revision', 'v2'), ('dry_run', False)]:
            with self.subTest(key=key):
                altered = Intent(**(self.intent.__dict__ | {key: value}))
                self.assertNotEqual(digest(altered), digest(self.intent))

if __name__ == '__main__':
    unittest.main()
