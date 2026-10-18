-- Runtime hardening: explicit lifecycle/idempotency/audit invariants.
create index if not exists ix_run_events_run_stage on aiops.run_events(run_id,stage,sequence);
create index if not exists ix_gates_run_stage on aiops.gates(run_id,stage);
create index if not exists ix_evidence_run on aiops.evidence((provenance->>'run_id'),known_at desc);
create index if not exists ix_facts_known_at on aiops.twin_facts(node_id,known_at desc);
create index if not exists ix_observations_time on aiops.observations(observed_at desc);

create table if not exists aiops.run_checkpoints(
 run_id text primary key references aiops.runs(run_id),
 stage text not null,
 version bigint not null,
 workflow_id text,
 updated_at timestamptz not null default now()
);

create table if not exists aiops.demo_artifacts(
 artifact_id text primary key,
 run_id text not null references aiops.runs(run_id),
 artifact_type text not null,
 title text not null,
 sequence_no integer not null,
 caption text,
 payload jsonb not null default '{}',
 created_at timestamptz not null default now(),
 unique(run_id,artifact_type,sequence_no)
);
