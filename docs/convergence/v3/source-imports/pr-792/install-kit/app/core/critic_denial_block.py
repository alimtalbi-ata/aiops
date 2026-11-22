import hashlib
import json

def block_with_denial(conn, rid, expected_version, idem,
                      aid, cid, evidence_ids, policy_input,
                      transition, append_event, new):
    ids=sorted(set(evidence_ids))
    if not idem or not aid or not cid or not ids:
        raise ValueError("denial_block_missing_fields")
    if (not isinstance(policy_input,dict)
            or policy_input.get("critic_validated") is not False
            or policy_input.get("command")!="EXECUTE"):
        raise ValueError("denial_block_invalid_policy_input")

    payload={
        "run_id":rid,"analysis_id":aid,"critique_id":cid,
        "evidence_ids":ids,"policy_input":policy_input
    }
    digest=hashlib.sha256(json.dumps(
        payload,sort_keys=True,separators=(",",":")
    ).encode()).hexdigest()

    row=conn.execute(
        "SELECT status,version,mode FROM aiops.runs "
        "WHERE run_id=%s FOR UPDATE",(rid,)
    ).fetchone()
    if not row:
        raise ValueError("run_not_found")

    receipt=conn.execute(
        "SELECT run_id,command,response FROM aiops.command_receipts "
        "WHERE idempotency_key=%s",(idem,)
    ).fetchone()
    if receipt:
        response=receipt[2]
        if (receipt[0]!=rid or receipt[1]!="BLOCK"
                or response.get("denial_hash")!=digest):
            raise ValueError("denial_block_idempotency_conflict")
        journal=conn.execute(
            'SELECT analysis_id,evidence_ids,policy_input,denial_hash,status '
            'FROM aiops.critic_denial_resume '
            'WHERE run_id=%s AND critique_id=%s FOR UPDATE',
            (rid,cid)
        ).fetchone()
        outbox=conn.execute(
            'SELECT analysis_id,evidence_ids,policy_input '
            'FROM aiops.critic_denial_outbox '
            'WHERE run_id=%s AND critique_id=%s',
            (rid,cid)
        ).fetchone()
        if (not journal or journal[0]!=aid
                or sorted(journal[1])!=ids
                or journal[2]!=policy_input
                or journal[3]!=digest
                or journal[4]!='COMMITTED'
                or not outbox or outbox[0]!=aid
                or sorted(outbox[1])!=ids
                or outbox[2]!=policy_input):
            raise ValueError('denial_block_committed_replay_inconsistent')
        return dict(response,idempotent=True)

    prepared=conn.execute(
        'SELECT analysis_id,evidence_ids,policy_input,denial_hash,status '
        'FROM aiops.critic_denial_resume '
        'WHERE run_id=%s AND critique_id=%s FOR UPDATE',
        (rid,cid)
    ).fetchone()
    if not prepared:
        raise ValueError('denial_block_not_prepared')
    if (prepared[0]!=aid or sorted(prepared[1])!=ids
            or prepared[2]!=policy_input
            or prepared[3]!=digest
            or prepared[4]!='PREPARED'):
        raise ValueError('denial_block_preparation_conflict')

    status,version,mode=row
    if version!=expected_version:
        raise ValueError("stale_run_version")
    transition(status,"BLOCKED")

    verified=conn.execute("""
        SELECT 1 FROM aiops.critique_records q
        JOIN aiops.analysis_records a
          ON a.analysis_id=q.analysis_id
        WHERE q.critique_id=%s AND q.run_id=%s
          AND q.analysis_id=%s AND a.run_id=%s
          AND q.validated=false
    """,(cid,rid,aid,rid)).fetchone()
    if not verified:
        raise ValueError("critic_denial_not_verified")

    count=conn.execute(
        "SELECT count(*) FROM aiops.evidence "
        "WHERE evidence_id=any(%s)",(ids,)
    ).fetchone()[0]
    if count!=len(ids):
        raise ValueError("unknown_evidence")

    nv=version+1
    conn.execute(
        "UPDATE aiops.runs SET status='BLOCKED',version=%s "
        "WHERE run_id=%s",(nv,rid)
    )
    append_event(
        conn,rid,"RUN","STATE_TRANSITION","BLOCKED",
        decision="BLOCK",
        payload={"mode":mode,"expected_version":version,
                 "new_version":nv,"denial_hash":digest},
        event_key="command-"+idem
    )
    conn.execute("""
        INSERT INTO aiops.critic_denial_outbox
          (run_id,critique_id,analysis_id,evidence_ids,policy_input)
        VALUES (%s,%s,%s,%s,%s)
        ON CONFLICT (run_id,critique_id) DO NOTHING
    """,(rid,cid,aid,ids,json.dumps(policy_input)))

    stored=conn.execute("""
        SELECT analysis_id,evidence_ids,policy_input
        FROM aiops.critic_denial_outbox
        WHERE run_id=%s AND critique_id=%s
    """,(rid,cid)).fetchone()
    if (not stored or stored[0]!=aid
            or sorted(stored[1])!=ids
            or stored[2]!=policy_input):
        raise ValueError("denial_intent_conflict")

    response={
        "run_id":rid,"status":"BLOCKED","version":nv,
        "denial_hash":digest,"critique_id":cid
    }
    conn.execute("""
        INSERT INTO aiops.command_receipts
          (receipt_id,run_id,idempotency_key,command,response)
        VALUES (%s,%s,%s,'BLOCK',%s)
    """,(new("RCPT"),rid,idem,json.dumps(response)))
    committed=conn.execute(
        "UPDATE aiops.critic_denial_resume "
        "SET status='COMMITTED',committed_at=now() "
        "WHERE run_id=%s AND critique_id=%s "
        "AND status='PREPARED' "
        "RETURNING run_id",
        (rid,cid)
    ).fetchone()
    if not committed:
        raise ValueError('denial_block_commit_transition_failed')
    return dict(response,idempotent=False)
