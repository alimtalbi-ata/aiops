-- 018: Core-owned immutable terminal SIM-GLPI receipt, separate from Run state.
-- RG-ACME-18: only a PREPARED sandbox Run may atomically persist a terminal
-- simulated ticket and independently hashed Worker no-effect receipt.
-- The table is append-only; disable sandbox/forward-revert code on rollback.
-- Never delete immutable terminal evidence, restore over live PG16, or grant LIVE.
CREATE TABLE IF NOT EXISTS aiops.acme_sandbox_terminal_tickets (
 tenant_id text NOT NULL CHECK (tenant_id='ACME-TEST'),
 attempt_id text NOT NULL,
 incident_id text NOT NULL REFERENCES aiops.incidents(incident_id),
 run_id text NOT NULL REFERENCES aiops.runs(run_id),
 ticket_id text NOT NULL UNIQUE CHECK (ticket_id LIKE 'SIM-GLPI-%'),
 proposal_id text NOT NULL,
 approval_id text NOT NULL CHECK (approval_id LIKE 'SIM-APP-%'),
 approval_issued_at timestamptz NOT NULL,
 approval_expires_at timestamptz NOT NULL,
 approval_nonce_sha256 char(64) NOT NULL UNIQUE
  CHECK (approval_nonce_sha256 ~ '^[0-9a-f]{64}$'),
 CHECK (approval_expires_at > approval_issued_at AND
        approval_expires_at <= approval_issued_at + interval '5 minutes'),
 worker_receipt_sha256 char(64) NOT NULL
  CHECK (worker_receipt_sha256 ~ '^[0-9a-f]{64}$'),
 worker_receipt jsonb NOT NULL,
 ticket_status text NOT NULL CHECK (ticket_status='RESOLVED'),
 terminal_ticket_sha256 char(64) NOT NULL
  CHECK (terminal_ticket_sha256 ~ '^[0-9a-f]{64}$'),
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (tenant_id, attempt_id),
 FOREIGN KEY (tenant_id,attempt_id)
  REFERENCES aiops.acme_sandbox_attempts(tenant_id,attempt_id)
);
DROP TRIGGER IF EXISTS trg_acme_sandbox_terminal_immutable
 ON aiops.acme_sandbox_terminal_tickets;
CREATE TRIGGER trg_acme_sandbox_terminal_immutable BEFORE UPDATE OR DELETE
 ON aiops.acme_sandbox_terminal_tickets FOR EACH ROW
 EXECUTE FUNCTION aiops.prevent_itsm_xref_mutation();
