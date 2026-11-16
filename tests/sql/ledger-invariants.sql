-- Transactional invariant test. All fixtures are rolled back at the end.
BEGIN;

INSERT INTO aiops.runs(run_id,mode,scenario_id,status,idempotency_key)
VALUES('CI-LIVE-LEDGER-RUN','LIVE','CI-SCENARIO','CREATED','CI-LIVE-LEDGER-RUN-KEY');

INSERT INTO aiops.evidence(evidence_id,source,external_id,observed_at,claim,confidence,provenance,payload_hash,payload)
VALUES('CI-EVIDENCE','ci-fixture','CI-EVIDENCE-EXT',now(),'Synthetic CI fixture: multipath is degraded.',0.99,'{"synthetic":false}'::jsonb,'ci-fixture-hash','{"metric":"path_state","value":"DEGRADED"}'::jsonb);

INSERT INTO aiops.analysis_records(
 analysis_id,run_id,incident_id,idempotency_key,revision,contract_version,provider,model,prompt_version,
 evidence_ids,evidence_set_hash,output,confidence,status
) VALUES (
 'CI-ANALYSIS','CI-LIVE-LEDGER-RUN',null,'CI-ANALYSIS-IDEM',1,'2.0','ci','fake','ci-test',
 '["CI-EVIDENCE"]'::jsonb,'ci-evidence-hash',
 '{"classification":"storage-path","severity":"P1","recommended_actions":[{"action_id":"A1","intent":"restore a degraded path","risk_tier":"CRITICAL","target_ci_id":"ACME-SAN-FABRIC-A","evidence_ids":["CI-EVIDENCE"],"preconditions":["ownership verified","fencing verified"],"expected_effect":"path restored","verification_steps":["query multipath state"],"rollback_plan":{"steps":["restore previous path state"]},"requires_human_approval":true,"advisory_only":true}]}'::jsonb,
 0.95,'VALID'
);

INSERT INTO aiops.critique_records(
 critique_id,idempotency_key,analysis_id,run_id,contract_version,provider,model,validated,issues,evidence_ids,output,diagnostic_confidence
) VALUES (
 'CI-CRITIQUE','CI-CRITIQUE-IDEM','CI-ANALYSIS','CI-LIVE-LEDGER-RUN','2.0','ci','fake',true,'[]'::jsonb,'["CI-EVIDENCE"]'::jsonb,
 '{"validated":true,"issues":[],"unsafe_actions":[],"claim_checks":[],"final_recommendation":"HUMAN_APPROVAL"}'::jsonb,0.93
);

INSERT INTO aiops.action_proposals(
 proposal_id,run_id,analysis_id,critique_id,source_action_id,proposal_revision,target_ci_id,action_type,risk_tier,
 parameters,evidence_ids,preconditions,expected_postconditions,rollback_plan,proposal_hash,status,expires_at
) VALUES (
 'CI-PROPOSAL','CI-LIVE-LEDGER-RUN','CI-ANALYSIS','CI-CRITIQUE','A1',1,'ACME-SAN-FABRIC-A','FAILOVER_PATH','CRITICAL',
 '{}'::jsonb,'["CI-EVIDENCE"]'::jsonb,'["ownership verified","fencing verified"]'::jsonb,'["multipath paths restored"]'::jsonb,
 '{"steps":["restore previous path state"]}'::jsonb,'CI-PROPOSAL-HASH','PROPOSED',now()+interval '30 minutes'
);

DO $$
BEGIN
 BEGIN
  UPDATE aiops.action_proposals SET status='APPROVED' WHERE proposal_id='CI-PROPOSAL';
  RAISE EXCEPTION 'TEST_FAILED: proposal approved without any approval';
 EXCEPTION WHEN OTHERS THEN
  IF SQLERRM LIKE 'TEST_FAILED:%' THEN RAISE; END IF;
  IF position('approval record bound to exact proposal hash and scope' in SQLERRM)=0 THEN RAISE; END IF;
 END;
END $$;

INSERT INTO aiops.approval_records(approval_id,proposal_id,proposal_hash,actor_id,actor_role,decision,scope,nonce,expires_at,audit)
VALUES('CI-APPROVAL-1','CI-PROPOSAL','CI-PROPOSAL-HASH','reviewer-1','security_admin','APPROVE',
 '{"proposal_hash":"CI-PROPOSAL-HASH","target_ci_id":"ACME-SAN-FABRIC-A","action_type":"FAILOVER_PATH"}'::jsonb,
 'CI-APPROVAL-NONCE-1',now()+interval '20 minutes','{"source":"ci"}'::jsonb);

DO $$
BEGIN
 BEGIN
  UPDATE aiops.action_proposals SET status='APPROVED' WHERE proposal_id='CI-PROPOSAL';
  RAISE EXCEPTION 'TEST_FAILED: critical proposal approved with one approver';
 EXCEPTION WHEN OTHERS THEN
  IF SQLERRM LIKE 'TEST_FAILED:%' THEN RAISE; END IF;
  IF position('critical proposal requires security_admin and incident_commander approvals' in SQLERRM)=0 THEN RAISE; END IF;
 END;
END $$;

INSERT INTO aiops.approval_records(approval_id,proposal_id,proposal_hash,actor_id,actor_role,decision,scope,nonce,expires_at,audit)
VALUES('CI-APPROVAL-2','CI-PROPOSAL','CI-PROPOSAL-HASH','reviewer-2','incident_commander','APPROVE',
 '{"proposal_hash":"CI-PROPOSAL-HASH","target_ci_id":"ACME-SAN-FABRIC-A","action_type":"FAILOVER_PATH"}'::jsonb,
 'CI-APPROVAL-NONCE-2',now()+interval '20 minutes','{"source":"ci"}'::jsonb);

UPDATE aiops.action_proposals SET status='APPROVED' WHERE proposal_id='CI-PROPOSAL';

DO $$
BEGIN
 BEGIN
  UPDATE aiops.action_proposals SET proposal_hash='TAMPERED-HASH' WHERE proposal_id='CI-PROPOSAL';
  RAISE EXCEPTION 'TEST_FAILED: proposal hash was mutable';
 EXCEPTION WHEN OTHERS THEN
  IF SQLERRM LIKE 'TEST_FAILED:%' THEN RAISE; END IF;
  IF position('proposal identity and hash are immutable' in SQLERRM)=0 THEN RAISE; END IF;
 END;
END $$;

INSERT INTO aiops.effect_receipts(effect_id,proposal_id,approval_id,idempotency_key,executor_id,adapter_version,outcome,result)
VALUES('CI-EFFECT','CI-PROPOSAL','CI-APPROVAL-1','CI-EFFECT-IDEM','ci-qualified-executor','fixture-1','STARTED','{}'::jsonb);

UPDATE aiops.effect_receipts SET outcome='SUCCEEDED',completed_at=now(),result='{"receipt":"fixture-only"}'::jsonb WHERE effect_id='CI-EFFECT';

INSERT INTO aiops.verification_records(verification_id,proposal_id,effect_id,outcome,expected,observed,evidence_ids,verifier_version,residual_risk)
VALUES('CI-VERIFY','CI-PROPOSAL','CI-EFFECT','PASS','{"paths":2}'::jsonb,'{"paths":2}'::jsonb,'["CI-EVIDENCE"]'::jsonb,'ci-verifier-1','{}'::jsonb);

INSERT INTO aiops.reconciliation_records(reconciliation_id,run_id,proposal_id,desired_state,observed_state,outcome,discrepancy,evidence_ids)
VALUES('CI-RECON','CI-LIVE-LEDGER-RUN','CI-PROPOSAL','{"paths":2}'::jsonb,'{"paths":2}'::jsonb,'CONVERGED','{}'::jsonb,'["CI-EVIDENCE"]'::jsonb);

INSERT INTO aiops.learning_cases(
 learning_case_id,idempotency_key,source_run_id,revision,case_type,synthetic,human_reviewed,outcome_verified,gold_eligible,
 label,evidence_ids,analysis_id,critique_id,verification_id,reviewed_at,reviewed_by,review_note
) VALUES (
 'CI-LEARNING-GOLD','CI-LEARNING-IDEM','CI-LIVE-LEDGER-RUN',1,'REMEDIATION',false,true,true,true,
 '{"label":"path restored"}'::jsonb,'["CI-EVIDENCE"]'::jsonb,'CI-ANALYSIS','CI-CRITIQUE','CI-VERIFY',now(),'reviewer-1','CI-only invariant test'
);

ROLLBACK;
