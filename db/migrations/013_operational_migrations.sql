create table if not exists aiops.schema_migrations(version text primary key, applied_at timestamptz not null default now());
alter table aiops.outbox_events add column if not exists locked_at timestamptz;
alter table aiops.outbox_events add column if not exists locked_by text;
create index if not exists ix_outbox_pending on aiops.outbox_events(status,available_at,created_at);
create index if not exists ix_evidence_run on aiops.evidence((provenance->>'run_id'));
