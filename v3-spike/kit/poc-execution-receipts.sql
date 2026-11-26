-- V3 isolated kit only: Core /execute persists a single workflow receipt per run.
-- Additive, no legacy migration or existing deployment changed.
CREATE TABLE IF NOT EXISTS aiops.execution_receipts (
    run_id text PRIMARY KEY REFERENCES aiops.runs(run_id),
    workflow_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
