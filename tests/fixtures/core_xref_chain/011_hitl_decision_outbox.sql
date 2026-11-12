-- 011 — Transactional HITL decision delivery outbox.
-- Decision persistence and outbox insertion share the approval transaction.
-- Worker delivery is leased and at-least-once; Temporal signals remain notifications,
-- never execution authorization.
create table if not exists aiops.hitl_decision_outbox (
    event_id text primary key,
    proposal_id text not null references aiops.action_proposals(proposal_id),
    run_id text not null references aiops.runs(run_id),
    proposal_hash text not null,
    proposal_revision integer not null check (proposal_revision >= 1),
    decision text not null check (decision in ('APPROVE','REJECT')),
    source_status text not null check (source_status in ('APPROVED','REJECTED','REVOKED')),
    approval_id text not null references aiops.approval_records(approval_id),
    status text not null default 'PENDING'
        check (status in ('PENDING','LEASED','DELIVERED','DEAD')),
    attempts integer not null default 0 check (attempts >= 0),
    available_at timestamptz not null default now(),
    lease_owner text,
    lease_token text,
    lease_until timestamptz,
    created_at timestamptz not null default now(),
    delivered_at timestamptz,
    last_error text,
    unique (proposal_id, proposal_hash, proposal_revision, decision)
);
create index if not exists ix_hitl_outbox_pending
    on aiops.hitl_decision_outbox(status, available_at, created_at);
create index if not exists ix_hitl_outbox_run
    on aiops.hitl_decision_outbox(run_id, created_at);
