"""Pure, fail-closed qualification of cross-plane AIOps2 lineage receipts.

This is a qualification contract, never an execution authorization.
"""
from dataclasses import dataclass
from enum import Enum

class Verdict(str, Enum):
    PASS = 'PASS'
    FAIL = 'FAIL'
    UNKNOWN = 'UNKNOWN'
    NOT_APPLICABLE = 'NOT_APPLICABLE'

@dataclass(frozen=True)
class Receipt:
    tenant_id: str
    incident_id: str
    run_id: str
    mode: str
    event_id: str
    evidence_ids: tuple[str, ...]
    analysis_id: str
    critic_decision_id: str
    policy_decision_id: str
    policy_state: str
    action_id: str | None
    temporal_run_id: str | None
    worker_run_id: str | None
    external_system: str
    external_ticket_id: str | None
    itsm_readback_verified: bool
    portal_run_id: str | None
    execution_expected: bool

@dataclass(frozen=True)
class Result:
    verdict: Verdict
    missing: tuple[str, ...]
    conflicts: tuple[str, ...]

def evaluate(value: object) -> Result:
    """Never infer success from a missing receipt or from Policy denial."""
    if not isinstance(value, Receipt):
        return Result(Verdict.UNKNOWN, ('receipt',), ())
    r = value
    if r.mode == 'LIVE':
        return Result(Verdict.FAIL, (), ('mode_live_not_qualifiable',))
    if r.mode != 'DEMO' or type(r.execution_expected) is not bool:
        return Result(Verdict.UNKNOWN, ('mode_or_execution_expected',), ())
    required = ('tenant_id','incident_id','run_id','event_id','analysis_id',
                'critic_decision_id','policy_decision_id','external_system',
                'external_ticket_id','portal_run_id')
    missing = [k for k in required if type(getattr(r,k)) is not str or not getattr(r,k).strip()]
    if type(r.evidence_ids) is not tuple or not r.evidence_ids or any(type(x) is not str or not x.strip() for x in r.evidence_ids):
        missing.append('evidence_ids')
    if type(r.itsm_readback_verified) is not bool or not r.itsm_readback_verified:
        missing.append('itsm_readback_verified')
    conflicts = []
    if r.portal_run_id and r.run_id and r.portal_run_id != r.run_id:
        conflicts.append('portal_run_mismatch')
    if r.policy_state in ('DENY','STOP_AUTO'):
        if r.execution_expected:
            conflicts.append('denied_execution_expected')
    elif r.policy_state != 'ALLOW':
        missing.append('policy_state')
    if r.execution_expected:
        for k in ('action_id','temporal_run_id','worker_run_id'):
            if type(getattr(r,k)) is not str or not getattr(r,k).strip():
                missing.append(k)
        for k in ('temporal_run_id','worker_run_id'):
            if getattr(r,k) and r.run_id and getattr(r,k) != r.run_id:
                conflicts.append(k+'_mismatch')
    elif any(getattr(r,k) is not None for k in ('action_id','temporal_run_id','worker_run_id')):
        conflicts.append('unexpected_execution_trace')
    if conflicts:
        return Result(Verdict.FAIL, tuple(missing), tuple(conflicts))
    if missing:
        return Result(Verdict.UNKNOWN, tuple(missing), ())
    return Result(Verdict.PASS, (), ())
