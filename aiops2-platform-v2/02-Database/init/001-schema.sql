CREATE TABLE IF NOT EXISTS incidents (
  id BIGSERIAL PRIMARY KEY,
  incident_id TEXT NOT NULL UNIQUE,
  idempotency_key TEXT NOT NULL UNIQUE,
  source TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  severity TEXT NOT NULL DEFAULT 'UNKNOWN',
  ci_id TEXT,
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  labels JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS incidents_created_at_idx ON incidents (created_at DESC);
CREATE INDEX IF NOT EXISTS incidents_severity_idx ON incidents (severity);
CREATE TABLE IF NOT EXISTS analyses (
  id BIGSERIAL PRIMARY KEY,
  incident_id TEXT NOT NULL REFERENCES incidents(incident_id) ON DELETE RESTRICT,
  analysis JSONB NOT NULL,
  policy JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS analyses_incident_id_idx ON analyses (incident_id);