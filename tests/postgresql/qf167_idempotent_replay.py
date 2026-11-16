import json
import psycopg
from critic_denial_prepare import prepare_critic_denial
from critic_denial_block import block_with_denial

DB="host=127.0.0.1 dbname=aiops user=aiops connect_timeout=5"
RID="RUN-QF167"
AID="ANL-QF167"
CID="CRT-QF167"
EID="EVD-QF167"
POLICY={"command":"EXECUTE","critic_validated":False}

with psycopg.connect(DB) as conn:
    try:
        c=conn
        c.execute("""
          INSERT INTO aiops.runs
          (run_id,mode,scenario_id,status,version,idempotency_key)
          VALUES (%s,'DEMO','SCN-QF167','RUNNING',3,%s)
        """,(RID,"RUN-IDEM-QF167"))
        c.execute("""
          INSERT INTO aiops.evidence
          (evidence_id,source,claim,confidence,payload_hash)
          VALUES (%s,'synthetic','QF167 synthetic',0.9,%s)
        """,(EID,__import__('hashlib').sha256(
            b'QF167-isolated-evidence-v1'
        ).hexdigest()))
        c.execute("""
          INSERT INTO aiops.analysis_records
          (analysis_id,run_id,idempotency_key,revision,contract_version,
           provider,model,prompt_version,evidence_set_hash,output,
           confidence,status)
          VALUES (%s,%s,%s,1,'2.1.0','synthetic','test','test',
                  %s,%s,0.9,'VALID')
        """,(AID,RID,"ANL-IDEM-QF167",'1'*64,json.dumps({})))
        c.execute("""
          INSERT INTO aiops.critique_records
          (critique_id,idempotency_key,analysis_id,run_id,
           contract_version,provider,model,validated,output,
           diagnostic_confidence)
          VALUES (%s,%s,%s,%s,'2.1.0','synthetic','test',
                  false,%s,0.9)
        """,(CID,"CRT-IDEM-QF167",AID,RID,json.dumps({})))

        prepared=prepare_critic_denial(
            c,RID,AID,CID,[EID],POLICY
        )
        assert prepared["status"]=="PREPARED"
        print("QF167_PREPARED=PASS")

        def transition(a,b):
            if (a,b)!=("RUNNING","BLOCKED"):
                raise ValueError("unexpected_transition")

        def event(conn,rid,stage,etype,status,**kw):
            conn.execute("""
              INSERT INTO aiops.run_events
              (event_id,run_id,sequence,stage,event_type,
               status,event_key,payload)
              VALUES ('EVT-QF167',%s,1,%s,%s,%s,%s,%s)
            """,(rid,stage,etype,status,
                 kw.get("event_key"),
                 json.dumps(kw.get("payload",{}))))

        blocked=block_with_denial(
            c,RID,3,"BLOCK-QF167",AID,CID,[EID],POLICY,
            transition,event,lambda x:x+"-QF167"
        )
        assert blocked["status"]=="BLOCKED"
        assert blocked["version"]==4
        print("QF167_BLOCKED=PASS")

        state=c.execute(
            "SELECT status,version FROM aiops.runs WHERE run_id=%s",
            (RID,)
        ).fetchone()
        journal=c.execute("""
            SELECT status,denial_hash,committed_at
            FROM aiops.critic_denial_resume
            WHERE run_id=%s
        """,(RID,)).fetchone()

        assert state==("BLOCKED",4),state
        assert journal[0]=="COMMITTED",journal
        assert journal[1]==prepared["denial_hash"]
        assert journal[2] is not None
        print("QF167_JOURNAL_COMMITTED=PASS")

        counts=c.execute("""
            SELECT
              (SELECT count(*) FROM aiops.run_events
               WHERE run_id=%s),
              (SELECT count(*) FROM aiops.command_receipts
               WHERE run_id=%s),
              (SELECT count(*) FROM aiops.critic_denial_outbox
               WHERE run_id=%s)
        """,(RID,RID,RID)).fetchone()

        assert counts==(1,1,1),counts
        print("QF167_ATOMIC_WRITES=PASS")

        replay=block_with_denial(
            c,RID,3,"BLOCK-QF167",AID,CID,[EID],POLICY,
            transition,event,lambda x:x+"-QF167"
        )
        assert replay["idempotent"] is True,replay
        assert replay["denial_hash"]==prepared["denial_hash"]
        print("QF167_IDENTICAL_REPLAY=PASS")

        changed=dict(POLICY,severity="ALTERED")
        try:
            block_with_denial(
                c,RID,3,"BLOCK-QF167",AID,CID,[EID],changed,
                transition,event,lambda x:x+"-QF167"
            )
        except ValueError as exc:
            assert str(exc)=="denial_block_idempotency_conflict",str(exc)
            print("QF167_CONFLICT_REJECTED=PASS")
        else:
            raise AssertionError("QF167_CONFLICT_ACCEPTED")

        after=c.execute("""
            SELECT
              (SELECT count(*) FROM aiops.run_events WHERE run_id=%s),
              (SELECT count(*) FROM aiops.command_receipts WHERE run_id=%s),
              (SELECT count(*) FROM aiops.critic_denial_outbox WHERE run_id=%s),
              (SELECT count(*) FROM aiops.critic_denial_resume WHERE run_id=%s)
        """,(RID,RID,RID,RID)).fetchone()

        assert after==(1,1,1,1),after
        print("QF167_NO_DUPLICATES=PASS")

    finally:
        conn.rollback()
        print("QF167_ROLLBACK=EXECUTED")
