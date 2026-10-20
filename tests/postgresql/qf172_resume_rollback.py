import hashlib
import json
import psycopg
from critic_denial_resume import resume_critic_denial

DB = "host=127.0.0.1 dbname=aiops user=aiops connect_timeout=5"
RID = "RUN-QF172"
AID = "ANL-QF172"
CID = "CRT-QF172"
EID = "EVD-QF172"
POLICY = {
    "mode": "DEMO",
    "command": "EXECUTE",
    "critic_validated": False,
    "evidence_count": 1
}
CRITIQUE = {
    "validated": False,
    "diagnostic_confidence": 0.9,
    "final_recommendation": "HUMAN_APPROVAL"
}

with psycopg.connect(DB) as c:
    try:
        c.execute(
            "INSERT INTO aiops.runs "
            "(run_id,mode,scenario_id,status,version,idempotency_key) "
            "VALUES (%s,'DEMO','SCN-QF172','RUNNING',3,%s)",
            (RID, "RUN-IDEM-QF172")
        )

        evidence_hash = hashlib.sha256(
            b"QF172-isolated-evidence-v1"
        ).hexdigest()

        c.execute(
            "INSERT INTO aiops.evidence "
            "(evidence_id,source,claim,confidence,payload_hash) "
            "VALUES (%s,'synthetic','QF172 synthetic',0.9,%s)",
            (EID, evidence_hash)
        )

        c.execute(
            "INSERT INTO aiops.analysis_records "
            "(analysis_id,run_id,idempotency_key,revision,contract_version,"
            "provider,model,prompt_version,evidence_ids,"
            "evidence_set_hash,output,confidence,status) "
            "VALUES (%s,%s,%s,1,'2.1.0','synthetic','test','test',"
            "%s,%s,%s,0.9,'VALID')",
            (
                AID, RID, "ANL-IDEM-QF172",
                json.dumps([EID]), "1" * 64, json.dumps({})
            )
        )

        c.execute(
            "INSERT INTO aiops.critique_records "
            "(critique_id,idempotency_key,analysis_id,run_id,"
            "contract_version,provider,model,validated,evidence_ids,"
            "output,diagnostic_confidence) "
            "VALUES (%s,%s,%s,%s,'2.1.0','synthetic','test',"
            "false,%s,%s,0.9)",
            (
                CID, "CRT-IDEM-QF172", AID, RID,
                json.dumps([EID]), json.dumps(CRITIQUE)
            )
        )

        c.execute(
            "INSERT INTO aiops.run_events "
            "(event_id,run_id,sequence,stage,event_type,status,"
            "event_key,evidence_ids,decision,confidence,payload) "
            "VALUES ('EVT-CRITIC-QF172',%s,1,'DGX_CRITIC',"
            "'CRITIC_COMPLETED','BLOCKED','DGX_CRITIC:COMPLETE',"
            "%s,'HUMAN_APPROVAL',0.9,%s)",
            (
                RID,
                json.dumps([EID]),
                json.dumps({
                    "analysis_record_id": AID,
                    "critique_record_id": CID,
                    "critique": CRITIQUE,
                    "denial_policy_input": POLICY
                })
            )
        )

        def transition(old, new):
            if (old, new) != ("RUNNING", "BLOCKED"):
                raise ValueError("unexpected_transition")

        def append_event(conn, rid, stage, etype, status, **kw):
            conn.execute(
                "INSERT INTO aiops.run_events "
                "(event_id,run_id,sequence,stage,event_type,status,"
                "event_key,payload) "
                "VALUES ('EVT-BLOCK-QF172',%s,2,%s,%s,%s,%s,%s)",
                (
                    rid, stage, etype, status,
                    kw.get("event_key"),
                    json.dumps(kw.get("payload") or {})
                )
            )

        ledger = c.execute(
            "SELECT q.output,q.evidence_ids,q.validated,"
            "a.status,a.evidence_ids "
            "FROM aiops.critique_records q "
            "JOIN aiops.analysis_records a "
            "ON a.analysis_id=q.analysis_id "
            "WHERE q.run_id=%s AND q.critique_id=%s "
            "AND q.analysis_id=%s AND a.run_id=%s",
            (RID,CID,AID,RID)
        ).fetchone()

        event = c.execute(
            "SELECT payload,evidence_ids,decision,confidence "
            "FROM aiops.run_events "
            "WHERE run_id=%s AND event_key='DGX_CRITIC:COMPLETE'",
            (RID,)
        ).fetchone()

        assert ledger is not None
        assert event is not None

        output,critic_ids,validated,analysis_status,analysis_ids=ledger
        payload,event_ids,decision,confidence=event
        critique=payload["critique"]

        checks={
            "validated_false":validated is False,
            "analysis_valid":analysis_status=="VALID",
            "output_equal":output==critique,
            "critic_evidence_equal":sorted(critic_ids)==sorted(event_ids),
            "analysis_evidence_equal":sorted(analysis_ids)==sorted(event_ids),
            "decision_equal":decision==critique.get("final_recommendation"),
            "confidence_equal":confidence==critique.get("diagnostic_confidence"),
        }

        for name,ok in checks.items():
            print("QF173_"+name.upper()+"="+str(ok))

        if not all(checks.values()):
            print("QF173_CONFIDENCE_TYPES=",
                  type(confidence).__name__,
                  type(critique.get("diagnostic_confidence")).__name__)

        result = resume_critic_denial(
            c, RID, transition, append_event,
            lambda prefix: prefix + "-QF172"
        )

        assert result["status"] == "BLOCKED", result
        assert result["version"] == 4, result
        assert result["recovered"] is True
        print("QF172_RESUME=PASS")

        state = c.execute(
            "SELECT status,version FROM aiops.runs WHERE run_id=%s",
            (RID,)
        ).fetchone()

        journal = c.execute(
            "SELECT status,denial_hash,committed_at "
            "FROM aiops.critic_denial_resume WHERE run_id=%s",
            (RID,)
        ).fetchone()

        assert state == ("BLOCKED", 4), state
        assert journal[0] == "COMMITTED", journal
        assert journal[1] == result["denial_hash"]
        assert journal[2] is not None
        print("QF172_COMMITTED=PASS")

        counts = c.execute(
            "SELECT "
            "(SELECT count(*) FROM aiops.run_events WHERE run_id=%s),"
            "(SELECT count(*) FROM aiops.command_receipts WHERE run_id=%s),"
            "(SELECT count(*) FROM aiops.critic_denial_outbox WHERE run_id=%s),"
            "(SELECT count(*) FROM aiops.critic_denial_resume WHERE run_id=%s)",
            (RID, RID, RID, RID)
        ).fetchone()

        assert counts == (2, 1, 1, 1), counts
        print("QF172_ATOMIC_WRITES=PASS")
    finally:
        c.rollback()
        print("QF172_ROLLBACK=EXECUTED")
