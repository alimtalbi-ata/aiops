BEGIN;

CREATE TABLE IF NOT EXISTS aiops.critic_denial_resume (
  run_id text NOT NULL REFERENCES aiops.runs(run_id),
  critique_id text NOT NULL REFERENCES aiops.critique_records(critique_id),
  analysis_id text NOT NULL REFERENCES aiops.analysis_records(analysis_id),
  evidence_ids text[] NOT NULL,
  policy_input jsonb NOT NULL,
  denial_hash text NOT NULL,
  status text NOT NULL DEFAULT 'PREPARED'
    CHECK (status IN ('PREPARED','COMMITTED')),
  prepared_at timestamptz NOT NULL DEFAULT now(),
  committed_at timestamptz,
  PRIMARY KEY (run_id, critique_id),
  CHECK (cardinality(evidence_ids)>0),
  CHECK (length(denial_hash)=64)
);

CREATE INDEX IF NOT EXISTS ix_critic_denial_resume_status
  ON aiops.critic_denial_resume(status,prepared_at);

COMMIT;
