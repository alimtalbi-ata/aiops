import json
import psycopg
from critic_denial_prepare import prepare_critic_denial
from critic_denial_block import block_with_denial

DB="host=127.0.0.1 dbname=aiops user=aiops connect_timeout=5"
RID="RUN-QF165"
AID="ANL-QF165"
CID="CRT-QF165"
EID="EVD-QF165"
POLICY={"command":"EXECUTE","critic_validated":False}

with psycopg.connect(DB) as conn:
    try:
        c=conn
        c.execute("""
          INSERT INTO aiops.runs
          (run_id,mode,scenario_id,status,version,idempotency_key)
          VALUES (%s,'DEMO','SCN-QF165','RUNNING',3,%s)
        """,(RID,"RUN-IDEM-QF165"))
        c.execute("""
          INSERT INTO aiops.evidence
          (evidence_id,source,claim,confidence,payload_hash)
          VALUES (%s,'synthetic','QF165 synthetic',0.9,%s)
        """,(EID,__import__('hashlib').sha256(
            b'QF165-isolated-evidence-v1'
        ).hexdigest()))
        c.execute("""
          INSERT INTO aiops.analysis_records
          (analysis_id,run_id,idempotency_key,revision,contract_version,
           provider,model,prompt_version,evidence_set_hash,output,
           confidence,status)
          VALUES (%s,%s,%s,1,'2.1.0','synthetic','test','test',
                  %s,%s,0.9,'VALID')
        """,(AID,RID,"ANL-IDEM-QF165",'1'*64,json.dumps({})))
        c.execute("""
          INSERT INTO aiops.critique_records
          (critique_id,idempotency_key,analysis_id,run_id,
           contract_version,provider,model,validated,output,
           diagnostic_confidence)
          VALUES (%s,%s,%s,%s,'2.1.0','synthetic','test',
                  false,%s,0.9)
        """,(CID,"CRT-IDEM-QF165",AID,RID,json.dumps({})))

        prepared=prepare_critic_denial(
            c,RID,AID,CID,[EID],POLICY
        )
        assert prepared["status"]=="PREPARED"
        print("QF165_PREPARED=PASS")

        def transition(a,b):
            if (a,b)!=("RUNNING","BLOCKED"):
                raise ValueError("unexpected_transition")

        def event(conn,rid,stage,etype,status,**kw):
            conn.execute("""
              INSERT INTO aiops.run_events
              (event_id,run_id,sequence,stage,event_type,
               status,event_key,payload)
              VALUES ('EVT-QF165',%s,1,%s,%s,%s,%s,%s)
            """,(rid,stage,etype,status,
                 kw.get("event_key"),
                 json.dumps(kw.get("payload",{}))))

        class FaultConnection:
            def __init__(self,real):
                self.real=real
            def execute(self,sql,params=None):
                if ('UPDATE aiops.critic_denial_resume' in sql
                        and "SET status='COMMITTED'" in sql):
                    raise RuntimeError('QF165_INJECTED_FAILURE')
                return self.real.execute(sql,params)

        blocked=block_with_denial(
            FaultConnection(c),RID,3,"BLOCK-QF165",AID,CID,[EID],POLICY,
            transition,event,lambda x:x+"-QF165"
        )
        assert blocked["status"]=="BLOCKED"
        assert blocked["version"]==4
        print("QF165_BLOCKED=PASS")

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
        print("QF165_JOURNAL_COMMITTED=PASS")

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
        print("QF165_ATOMIC_WRITES=PASS")
    finally:
        conn.rollback()
        print("QF165_ROLLBACK=EXECUTED")
