create table if not exists aiops.execution_receipts(
 run_id text primary key references aiops.runs(run_id),
 workflow_id text not null unique,
 started_at timestamptz not null default now()
);
