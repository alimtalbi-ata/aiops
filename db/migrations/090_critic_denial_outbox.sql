-- Worker V2.7: transactionally durable terminal Critic denials.
-- IMPORTANT: apply via an explicit migration on an isolated database.
-- PostgreSQL docker-entrypoint-initdb.d scripts do not rerun on existing volumes.
BEGIN;
CREATE TABLE IF NOT EXISTS aiops.critic_denial_outbox (
  run_id text NOT NULL REFERENCES aiops.runs(run_id),
  critique_id text NOT NULL REFERENCES aiops.critique_records(critique_id),
  analysis_id text NOT NULL REFERENCES aiops.analysis_records(analysis_id),
  evidence_ids text[] NOT NULL,
  policy_input jsonb NOT NULL,
  status text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','RECONCILED')),
  policy_decision_id text REFERENCES aiops.policy_decisions(policy_decision_id),
  attempts integer NOT NULL DEFAULT 0,
  last_error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  reconciled_at timestamptz,
  PRIMARY KEY(run_id, critique_id),
  CHECK (cardinality(evidence_ids) > 0)
);
CREATE INDEX IF NOT EXISTS critic_denial_outbox_pending_idx
 ON aiops.critic_denial_outbox(created_at) WHERE status='PENDING';
COMMIT;
