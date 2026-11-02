-- 018 RG-ACME-08/09: append-only synthetic SIM-GLPI ticket transitions.
-- Apply after 017 in a single transaction on disposable PG16.
-- Rollback: disable AIOPS_ACME_SANDBOX_ENABLED and revert application code;
-- preserve 013-018 immutable audit and backups. No destructive DOWN.
create table if not exists aiops.acme_sandbox_ticket_events (
 tenant_id text not null check (tenant_id='ACME-TEST'),
 attempt_id text not null,
 transition_seq smallint not null check (transition_seq in (1,2)),
 status text not null check (status in ('PREPARED','RESOLVED')),
 ticket_id text not null check (ticket_id like 'SIM-GLPI-%'),
 incident_id text not null references aiops.incidents(incident_id),
 run_id text not null references aiops.runs(run_id),
 proposal_id text not null,
 approval_id text,
 worker_receipt_sha256 char(64),
 recorded_at timestamptz not null default now(),
 primary key (tenant_id,attempt_id,transition_seq),
 unique (tenant_id,attempt_id,status),
 foreign key (tenant_id,attempt_id)
   references aiops.acme_sandbox_attempts(tenant_id,attempt_id),
 constraint acme_ticket_transition_binding check (
   (transition_seq=1 and status='PREPARED'
      and approval_id is null and worker_receipt_sha256 is null)
   or (transition_seq=2 and status='RESOLVED'
      and approval_id like 'SIM-APP-%'
      and worker_receipt_sha256 ~ '^[0-9a-f]{64}$'))
);
drop trigger if exists trg_acme_ticket_events_immutable on aiops.acme_sandbox_ticket_events;
create trigger trg_acme_ticket_events_immutable before update or delete
 on aiops.acme_sandbox_ticket_events for each row
 execute function aiops.prevent_itsm_xref_mutation();
