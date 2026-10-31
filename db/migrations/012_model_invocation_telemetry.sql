-- 012 — Persist provider-reported model invocation telemetry with immutable AI records.
-- Token counts and costs remain NULL when the provider does not report them.
ALTER TABLE aiops.analysis_records
  ADD COLUMN IF NOT EXISTS model_invocation jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE aiops.critique_records
  ADD COLUMN IF NOT EXISTS model_invocation jsonb NOT NULL DEFAULT '{}'::jsonb;
