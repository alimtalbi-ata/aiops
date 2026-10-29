def valid_denial_command(policy):
    if not isinstance(policy, dict):
        return False
    expected = {
        "DEMO": "OBSERVE",
        "REPLAY": "OBSERVE",
        "STORY": "OBSERVE",
        "LIVE": "EXECUTE",
    }
    mode = policy.get("mode")
    return mode in expected and policy.get("command") == expected[mode]


import json
from decimal import Decimal, InvalidOperation

from core.critic_denial_prepare import prepare_critic_denial
from core.critic_denial_block import block_with_denial


def equal_confidence(stored, reported):
    try:
        left=Decimal(str(stored))
        right=Decimal(str(reported))
    except (InvalidOperation, ValueError, TypeError):
        return False
    return (
        left.is_finite()
        and right.is_finite()
        and Decimal("0") <= left <= Decimal("1")
        and left == right
    )


def resume_critic_denial(conn, rid, transition, append_event, new):
    run = conn.execute(
        "SELECT status,version,mode FROM aiops.runs "
        "WHERE run_id=%s FOR UPDATE",
        (rid,)
    ).fetchone()
    if not run:
        raise ValueError("denial_resume_run_not_found")

    status, version, mode = run
    if status not in ("RUNNING", "BLOCKED"):
        raise ValueError("denial_resume_invalid_run_state")

    event = conn.execute("""
        SELECT payload,evidence_ids,status,decision,confidence
        FROM aiops.run_events
        WHERE run_id=%s
          AND stage='DGX_CRITIC'
          AND event_type='CRITIC_COMPLETED'
          AND event_key='DGX_CRITIC:COMPLETE'
    """, (rid,)).fetchone()
    if not event:
        raise ValueError("denial_resume_critic_event_missing")

    payload, evidence_ids, event_status, decision, confidence = event
    if not isinstance(payload, dict) or event_status != "BLOCKED":
        raise ValueError("denial_resume_event_invalid")

    aid = payload.get("analysis_record_id")
    cid = payload.get("critique_record_id")
    policy = payload.get("denial_policy_input")
    critique = payload.get("critique")

    if (not isinstance(aid, str) or not aid
            or not isinstance(cid, str) or not cid
            or not isinstance(critique, dict)
            or not isinstance(policy, dict)
            or not isinstance(evidence_ids, list)
            or not evidence_ids
            or len(evidence_ids) != len(set(evidence_ids))):
        raise ValueError("denial_resume_snapshot_incomplete")

    ids = sorted(evidence_ids)

    if (policy.get("mode") != mode
            or not valid_denial_command(policy)
            or policy.get("critic_validated") is not False
            or policy.get("evidence_count") != len(ids)
            or critique.get("validated") is not False):
        raise ValueError("denial_resume_policy_inconsistent")

    ledger = conn.execute("""
        SELECT q.output,q.evidence_ids,q.validated,
               a.status,a.evidence_ids
        FROM aiops.critique_records q
        JOIN aiops.analysis_records a
          ON a.analysis_id=q.analysis_id
        WHERE q.run_id=%s AND q.critique_id=%s
          AND q.analysis_id=%s AND a.run_id=%s
    """, (rid, cid, aid, rid)).fetchone()

    if not ledger:
        raise ValueError("denial_resume_ledger_missing")

    output, critic_ids, validated, analysis_status, analysis_ids = ledger

    if (validated is not False
            or analysis_status != "VALID"
            or output != critique
            or sorted(critic_ids) != ids
            or sorted(analysis_ids) != ids
            or decision != critique.get("final_recommendation")
            or not equal_confidence(confidence, critique.get("diagnostic_confidence"))):
        raise ValueError("denial_resume_ledger_inconsistent")

    prepared = prepare_critic_denial(
        conn, rid, aid, cid, ids, policy
    )

    result = block_with_denial(
        conn, rid, version, "CRITIC-BLOCK-" + rid,
        aid, cid, ids, policy,
        transition, append_event, new
    )

    if result.get("denial_hash") != prepared["denial_hash"]:
        raise ValueError("denial_resume_hash_mismatch")

    return dict(
        result,
        analysis_id=aid,
        prepared_idempotent=prepared["idempotent"],
        recovered=True
    )
