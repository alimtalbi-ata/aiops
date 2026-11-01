-- 014 Core-owned terminal REJECT audit. Strictly after installed 001/004/009-013.
-- Never DROP 013 or delete any terminal audit rows on application rollback.
-- This table is a permanent append-only record of notification exhaustion,
-- not a human approval, delivery receipt, or authorization to execute.
create table if not exists aiops.hitl_reject_terminal_receipts (
 event_id text primary key references aiops.hitl_decision_outbox(event_id),
 schema_version text not null default 'aiops.core-hitl-reject-terminal-receipt.v1'
   check (schema_version='aiops.core-hitl-reject-terminal-receipt.v1'),
 tenant_id text not null,
 run_id text not null references aiops.runs(run_id),
 proposal_id text not null references aiops.action_proposals(proposal_id),
 proposal_hash char(64) not null check (proposal_hash ~ '^[0-9a-f]{64}$'),
 proposal_revision integer not null check (proposal_revision >= 1),
 actor_id text not null,
 lease_owner text not null,
 lease_token_sha256 char(64) not null check (lease_token_sha256 ~ '^[0-9a-f]{64}$'),
 attempts integer not null check (attempts >= 8),
 lease_expired_at timestamptz not null,
 dead_at timestamptz not null,
 receipt_payload jsonb not null,
 receipt_sha256 char(64) not null check (receipt_sha256 ~ '^[0-9a-f]{64}$'),
 check (lease_expired_at <= dead_at)
);
create index if not exists ix_hitl_reject_terminal_tenant_run
 on aiops.hitl_reject_terminal_receipts(tenant_id,run_id,dead_at);
-- Reuse 012's installed immutable-audit trigger function.
drop trigger if exists trg_hitl_reject_terminal_immutable
 on aiops.hitl_reject_terminal_receipts;
create trigger trg_hitl_reject_terminal_immutable before update or delete
 on aiops.hitl_reject_terminal_receipts for each row
 execute function aiops.prevent_itsm_xref_mutation();
