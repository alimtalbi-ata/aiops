-- 016: isolated ACME-TEST SIMULATION attempt ledger; after 001/004/009-015.
-- Additive; never a real GLPI ticket, human approval or LIVE effect.
-- Rollback: disable route/revert code, preserve immutable synthetic facts.
create table if not exists aiops.acme_sandbox_attempts (
 tenant_id text not null check (tenant_id='ACME-TEST'),
 attempt_id text not null check (attempt_id ~ '^[A-Za-z0-9][A-Za-z0-9_-]{2,99}$'),
 request_sha256 char(64) not null check (request_sha256 ~ '^[0-9a-f]{64}$'),
 incident_id text not null unique references aiops.incidents(incident_id),
 run_id text not null unique references aiops.runs(run_id),
 ticket_id text not null unique check (ticket_id like 'SIM-GLPI-%'),
 proposal_id text not null unique check (proposal_id like 'PROP-SIM-%'),
 analysis_id text not null unique references aiops.analysis_records(analysis_id),
 critique_id text not null unique references aiops.critique_records(critique_id),
 ticket_status text not null check (ticket_status='RESOLVED'),
 source text not null check (source='SYNTHETIC_SIMULATOR'),
 evidence_count integer not null check (evidence_count>=2),
 source_event_count integer not null check (source_event_count=7),
 created_at timestamptz not null default now(),
 primary key (tenant_id,attempt_id)
);
create index if not exists ix_acme_sandbox_run on aiops.acme_sandbox_attempts(run_id,tenant_id);
drop trigger if exists trg_acme_sandbox_immutable on aiops.acme_sandbox_attempts;
create trigger trg_acme_sandbox_immutable before update or delete
 on aiops.acme_sandbox_attempts for each row
 execute function aiops.prevent_itsm_xref_mutation();
