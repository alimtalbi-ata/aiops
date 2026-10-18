-- V7.4: simulation isolation, integration outbox and gate integrity.
alter table aiops.observations add column if not exists run_id text references aiops.runs(run_id);
create index if not exists ix_observations_run on aiops.observations(run_id,observed_at desc);
create table if not exists aiops.outbox_events(
 outbox_id text primary key, run_id text references aiops.runs(run_id), event_type text not null,
 aggregate_type text not null, aggregate_id text not null, idempotency_key text not null unique,
 payload jsonb not null default '{}', status text not null default 'PENDING' check(status in('PENDING','SENDING','SENT','FAILED')),
 attempts integer not null default 0, available_at timestamptz not null default now(), sent_at timestamptz,
 last_error text, created_at timestamptz not null default now()
);
create index if not exists ix_outbox_pending on aiops.outbox_events(status,available_at);
