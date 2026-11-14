-- Core-owned immutable intent recorded BEFORE calling the Temporal Worker.
-- The record proves only what Core intended to send; it does not prove
-- Temporal received it or that a workflow started.
-- No update/delete path is exposed to the application.
CREATE TABLE IF NOT EXISTS aiops.execution_start_intents (
    run_id text PRIMARY KEY REFERENCES aiops.runs(run_id),
    mode text NOT NULL CHECK (mode IN ('LIVE','DEMO','REPLAY','STORY')),
    scenario_id text NOT NULL,
    start_version bigint NOT NULL CHECK (start_version >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (length(run_id) BETWEEN 1 AND 128),
    CHECK (length(scenario_id) BETWEEN 1 AND 128)
);
-- Operators must provision a restricted DB role: application UPDATE/DELETE
-- privileges on this table must be revoked before any LIVE qualification.
