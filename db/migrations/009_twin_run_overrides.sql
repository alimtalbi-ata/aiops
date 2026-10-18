create table if not exists aiops.twin_run_overrides(
 run_id text not null references aiops.runs(run_id),
 node_id text not null references aiops.twin_nodes(node_id),
 state text not null,
 health numeric check(health between 0 and 1),
 observed_at timestamptz not null default now(),
 known_at timestamptz not null default now(),
 payload jsonb not null default '{}',
 primary key(run_id,node_id)
);
create index if not exists ix_twin_overrides_run on aiops.twin_run_overrides(run_id);
