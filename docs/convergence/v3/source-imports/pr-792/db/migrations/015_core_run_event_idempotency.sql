-- 015 Core Run event idempotency bridge for installed 001/004/009-014.
-- The historical 008_event_idempotency.sql is NOT in that installed chain.
-- Additive only; compatible with an environment that already applied 008.
-- Transactional deployment: apply under a single transaction and verify index.
-- No DOWN/DROP: 013/014 audit and existing Run events must survive rollback.
DO $$
BEGIN
  IF to_regclass('aiops.run_events') IS NULL THEN
    RAISE EXCEPTION 'Core 001 run_events must be installed before 015';
  END IF;
END $$;
ALTER TABLE aiops.run_events ADD COLUMN IF NOT EXISTS event_key text;
CREATE UNIQUE INDEX IF NOT EXISTS ux_run_events_event_key
  ON aiops.run_events (run_id, event_key)
  WHERE event_key IS NOT NULL;
