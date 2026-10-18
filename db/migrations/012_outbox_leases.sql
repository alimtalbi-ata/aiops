alter table aiops.outbox_events add column if not exists locked_at timestamptz;
alter table aiops.outbox_events add column if not exists locked_by text;
create index if not exists ix_outbox_lease on aiops.outbox_events(status,locked_at);
create table if not exists aiops.integration_receipts(
 receipt_id text primary key, outbox_id text not null unique references aiops.outbox_events(outbox_id),
 target text not null, idempotency_key text not null unique, status text not null,
 response jsonb not null default '{}', created_at timestamptz not null default now()
);
