"""Atomic finalization of fenced Critic denials."""
import datetime
import hashlib
import json

from denial_fencing import validate_finalization


def finalize_denial(conn, rid, cid, owner, token, verdict):
    """Caller owns the transaction; never commit inside this function."""
    locked_run = conn.execute(
        "SELECT status FROM aiops.runs WHERE run_id=%s FOR UPDATE",
        (rid,)
    ).fetchone()
    if not locked_run or locked_run[0] != "BLOCKED":
        raise ValueError("run_not_blocked")

    row = conn.execute("""
        SELECT o.analysis_id,o.status,o.lease_owner,
               o.fencing_token,o.lease_expires_at,
               r.status,q.validated,o.evidence_ids,o.policy_input
        FROM aiops.critic_denial_outbox o
        JOIN aiops.runs r ON r.run_id=o.run_id
        JOIN aiops.critique_records q ON q.critique_id=o.critique_id
        WHERE o.run_id=%s AND o.critique_id=%s
          AND q.run_id=o.run_id AND q.analysis_id=o.analysis_id
        FOR UPDATE OF o, r
    """, (rid, cid)).fetchone()

    if not row:
        raise ValueError("denial_intent_not_found")

    keys = (
        "analysis_id","status","lease_owner","fencing_token",
        "lease_expires_at","run_status","critic_validated",
        "evidence_ids","policy_input"
    )
    data = dict(zip(keys,row))
    validate_finalization(
        data,owner,token,verdict,datetime.datetime.now(datetime.timezone.utc)
    )

    proof = {
        "analysis_id":data["analysis_id"],
        "critique_id":cid,
        "evidence_ids":sorted(data["evidence_ids"]),
        "policy_input":data["policy_input"]
    }
    canonical=json.dumps(
        {"run_id":rid,"policy":verdict,"proof":proof,
         "policy_version":"2.1.0"},
        sort_keys=True,separators=(",",":")
    )
    digest=hashlib.sha256(canonical.encode()).hexdigest()

    old=conn.execute("""
        SELECT policy_decision_id,decision,state,analysis_id,critique_id
        FROM aiops.policy_decisions
        WHERE run_id=%s AND input_hash=%s
    """,(rid,digest)).fetchone()

    if old:
        if (old[1]!=verdict["decision"] or old[2]!=verdict["state"] or old[3]!=data["analysis_id"] or old[4]!=cid):
            raise ValueError("policy_decision_conflict")
        pid=old[0]
    else:
        pid="POL-"+digest[:16].upper()
        conn.execute("""
            INSERT INTO aiops.policy_decisions
            (policy_decision_id,run_id,analysis_id,critique_id,
             policy_version,input_hash,decision,state,
             reasons,proof_snapshot)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,(
            pid,rid,data["analysis_id"],cid,"2.1.0",digest,
            verdict["decision"],verdict["state"],
            json.dumps(verdict.get("reasons",[])),
            json.dumps(proof)
        ))

    conn.execute("""
        UPDATE aiops.critic_denial_outbox
        SET status='RECONCILED',
            policy_decision_id=%s,
            reconciled_at=now()
        WHERE run_id=%s AND critique_id=%s
    """,(pid,rid,cid))

    return {"status":"RECONCILED","policy_decision_id":pid}
