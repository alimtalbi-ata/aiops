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


import hashlib
import json

def prepare_critic_denial(
    conn,rid,aid,cid,evidence_ids,policy_input
):
    ids=sorted(set(evidence_ids))
    if not aid or not cid or not ids:
        raise ValueError('critic_denial_prepare_missing_fields')
    if (not isinstance(policy_input,dict)
            or policy_input.get('critic_validated') is not False
            or not valid_denial_command(policy_input)):
        raise ValueError('critic_denial_prepare_invalid_policy')

    payload={
        'run_id':rid,'analysis_id':aid,'critique_id':cid,
        'evidence_ids':ids,'policy_input':policy_input
    }
    digest=hashlib.sha256(
        json.dumps(payload,sort_keys=True,separators=(',',':')).encode()
    ).hexdigest()

    row=conn.execute(
        'SELECT status,mode FROM aiops.runs WHERE run_id=%s FOR UPDATE',
        (rid,)
    ).fetchone()
    if not row or row[0] not in ('RUNNING','BLOCKED'):
        raise ValueError('critic_denial_prepare_invalid_run')
    if policy_input.get('mode') != row[1]:
        raise ValueError('critic_denial_prepare_mode_mismatch')

    valid=conn.execute("""
        SELECT 1
        FROM aiops.critique_records q
        JOIN aiops.analysis_records a
          ON a.analysis_id=q.analysis_id
        WHERE q.run_id=%s AND q.critique_id=%s
          AND q.analysis_id=%s AND a.run_id=%s
          AND q.validated=false
    """,(rid,cid,aid,rid)).fetchone()
    if not valid:
        raise ValueError('critic_denial_prepare_unverified_critic')

    count=conn.execute(
        'SELECT count(*) FROM aiops.evidence WHERE evidence_id=any(%s)',
        (ids,)
    ).fetchone()[0]
    if count!=len(ids):
        raise ValueError('critic_denial_prepare_unknown_evidence')

    old=conn.execute("""
        SELECT analysis_id,evidence_ids,policy_input,denial_hash,status
        FROM aiops.critic_denial_resume
        WHERE run_id=%s AND critique_id=%s
    """,(rid,cid)).fetchone()

    if old:
        if (old[0]!=aid or sorted(old[1])!=ids
                or old[2]!=policy_input or old[3]!=digest):
            raise ValueError('critic_denial_prepare_conflict')
        return {
            'run_id':rid,'critique_id':cid,
            'denial_hash':digest,'status':old[4],
            'idempotent':True
        }

    conn.execute("""
        INSERT INTO aiops.critic_denial_resume
          (run_id,critique_id,analysis_id,evidence_ids,
           policy_input,denial_hash)
        VALUES (%s,%s,%s,%s,%s,%s)
    """,(rid,cid,aid,ids,json.dumps(policy_input),digest))

    return {
        'run_id':rid,'critique_id':cid,
        'denial_hash':digest,'status':'PREPARED',
        'idempotent':False
    }
