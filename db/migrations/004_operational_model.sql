-- ACME AioOps 2.0 operational model: business/service/application layers,
-- bi-temporal facts, incidents, observations, changes, impacts and demo scenarios.
create table if not exists aiops.twin_facts(
 fact_id text primary key,
 node_id text not null references aiops.twin_nodes(node_id),
 attribute text not null,
 value jsonb not null,
 valid_from timestamptz not null,
 valid_to timestamptz,
 known_at timestamptz not null default now(),
 source_evidence_id text references aiops.evidence(evidence_id),
 confidence numeric not null check(confidence between 0 and 1)
);
create index if not exists ix_twin_facts_node_time on aiops.twin_facts(node_id,valid_from,known_at desc);

create table if not exists aiops.incidents(
 incident_id text primary key,
 external_id text unique,
 title text not null,
 severity text not null check(severity in('P1','P2','P3','P4','UNKNOWN')),
 state text not null check(state in('OPEN','ACKNOWLEDGED','INVESTIGATING','MITIGATED','RESOLVED','CLOSED')),
 service_id text references aiops.twin_nodes(node_id),
 opened_at timestamptz not null,
 resolved_at timestamptz,
 source text not null,
 synthetic boolean not null default true,
 payload jsonb not null default '{}'
);
create index if not exists ix_incidents_service_state on aiops.incidents(service_id,state);

create table if not exists aiops.observations(
 observation_id text primary key,
 node_id text references aiops.twin_nodes(node_id),
 metric text not null,
 value numeric,
 unit text,
 observed_at timestamptz not null,
 known_at timestamptz not null default now(),
 status text not null check(status in('OK','WARN','CRITICAL','UNKNOWN')),
 evidence_id text references aiops.evidence(evidence_id),
 payload jsonb not null default '{}'
);
create index if not exists ix_observations_node_metric_time on aiops.observations(node_id,metric,observed_at desc);

create table if not exists aiops.changes(
 change_id text primary key,
 external_id text unique,
 title text not null,
 state text not null check(state in('PLANNED','IN_PROGRESS','COMPLETED','FAILED','ROLLED_BACK')),
 started_at timestamptz,
 completed_at timestamptz,
 actor text,
 affected_nodes jsonb not null default '[]',
 synthetic boolean not null default true,
 payload jsonb not null default '{}'
);
create index if not exists ix_changes_time on aiops.changes(started_at desc);

create table if not exists aiops.impact_assessments(
 assessment_id text primary key,
 run_id text references aiops.runs(run_id),
 incident_id text references aiops.incidents(incident_id),
 service_id text references aiops.twin_nodes(node_id),
 impact_state text not null check(impact_state in('NONE','DEGRADED','OUTAGE','UNKNOWN')),
 score numeric not null check(score between 0 and 1),
 rationale text not null,
 evidence_ids jsonb not null default '[]',
 created_at timestamptz not null default now()
);

create table if not exists aiops.scenario_steps(
 scenario_id text not null references aiops.scenarios(scenario_id),
 step_no integer not null,
 at_seconds integer not null check(at_seconds>=0),
 action text not null,
 target_node_id text,
 payload jsonb not null default '{}',
 primary key(scenario_id,step_no)
);

create table if not exists aiops.run_stage_state(
 run_id text not null references aiops.runs(run_id),
 stage text not null,
 state text not null check(state in('PENDING','RUNNING','PASS','BLOCKED','FAIL','UNKNOWN')),
 attempt integer not null default 0,
 started_at timestamptz,
 completed_at timestamptz,
 last_error text,
 primary key(run_id,stage)
);

create table if not exists aiops.api_audit(
 audit_id text primary key,
 method text not null,
 path text not null,
 actor text not null,
 request_id text not null,
 status_code integer not null,
 created_at timestamptz not null default now(),
 payload jsonb not null default '{}'
);
