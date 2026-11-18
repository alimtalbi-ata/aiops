-- 017: Core PREPARED is a real persisted sandbox state, never a pre-emptive RESOLVED.
-- Apply after 016 transactionally; additive constraints, no table/volume deletion.
-- Rollback: disable AIOPS_ACME_SANDBOX_ENABLED, forward-revert code, retain audit.
ALTER TABLE aiops.incidents DROP CONSTRAINT IF EXISTS incidents_state_check;
ALTER TABLE aiops.incidents ADD CONSTRAINT incidents_state_check
 CHECK (state IN ('OPEN','ACKNOWLEDGED','INVESTIGATING','MITIGATED','PREPARED','RESOLVED','CLOSED'));
ALTER TABLE aiops.runs DROP CONSTRAINT IF EXISTS runs_status_check;
ALTER TABLE aiops.runs ADD CONSTRAINT runs_status_check
 CHECK (status IN ('CREATED','RUNNING','WAITING','BLOCKED','PREPARED','RESOLVED','FAILED','CANCELLED'));
ALTER TABLE aiops.acme_sandbox_attempts DROP CONSTRAINT IF EXISTS acme_sandbox_attempts_ticket_status_check;
ALTER TABLE aiops.acme_sandbox_attempts ADD CONSTRAINT acme_sandbox_attempts_ticket_status_check
 CHECK (ticket_status IN ('PREPARED','RESOLVED'));
