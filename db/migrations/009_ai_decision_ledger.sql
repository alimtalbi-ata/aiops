-- AIOps 2.0 canonical AI decision ledger.
create table if not exists aiops.analysis_records (
 analysis_id text primary key, run_id text not null references aiops.runs(run_id), incident_id text,
 idempotency_key text not null unique,
 revision integer not null check (revision >= 1), contract_version text not null,
 provider text not null, model text not null, prompt_version text not null,
 evidence_ids jsonb not null default '[]'::jsonb, evidence_set_hash text not null,
 output jsonb not null, confidence numeric not null check (confidence between 0 and 1),
 status text not null check (status in ('VALID','INVALID','UNAVAILABLE','SUPERSEDED')),
 created_at timestamptz not null default now(), unique(run_id, revision)
);
create index if not exists ix_analysis_run_created on aiops.analysis_records(run_id, created_at desc);
create table if not exists aiops.critique_records (
 critique_id text primary key, idempotency_key text not null unique, analysis_id text not null references aiops.analysis_records(analysis_id),
 run_id text not null references aiops.runs(run_id), contract_version text not null,
 provider text not null, model text not null, validated boolean not null,
 issues jsonb not null default '[]'::jsonb, evidence_ids jsonb not null default '[]'::jsonb,
 output jsonb not null, diagnostic_confidence numeric not null check (diagnostic_confidence between 0 and 1),
 created_at timestamptz not null default now()
);
create index if not exists ix_critique_run_created on aiops.critique_records(run_id, created_at desc);
create table if not exists aiops.policy_decisions (
 policy_decision_id text primary key, run_id text not null references aiops.runs(run_id),
 analysis_id text references aiops.analysis_records(analysis_id), critique_id text references aiops.critique_records(critique_id),
 policy_version text not null, input_hash text not null,
 decision text not null check (decision in ('OBSERVE','ENRICH','ESCALATE','HUMAN_APPROVAL','BLOCK','AUTO_REMEDIATE','SIMULATE','ALLOW')),
 state text not null check (state in ('PASS','FAIL','BLOCKED','UNKNOWN')),
 reasons jsonb not null default '[]'::jsonb, proof_snapshot jsonb not null default '{}'::jsonb,
 created_at timestamptz not null default now(), unique(run_id,input_hash)
);
create index if not exists ix_policy_decision_run on aiops.policy_decisions(run_id, created_at desc);
create table if not exists aiops.action_proposals (
 proposal_id text primary key, run_id text not null references aiops.runs(run_id),
 analysis_id text not null references aiops.analysis_records(analysis_id), critique_id text not null references aiops.critique_records(critique_id), source_action_id text not null,
 proposal_revision integer not null check (proposal_revision >= 1), target_ci_id text not null,
 action_type text not null, risk_tier text not null check (risk_tier in ('LOW','MEDIUM','HIGH','CRITICAL')),
 parameters jsonb not null default '{}'::jsonb, evidence_ids jsonb not null default '[]'::jsonb,
 preconditions jsonb not null default '[]'::jsonb, expected_postconditions jsonb not null default '[]'::jsonb,
 rollback_plan jsonb not null default '{}'::jsonb, proposal_hash text not null,
 status text not null check (status in ('PROPOSED','REJECTED','APPROVED','EXPIRED','EXECUTING','EXECUTED','FAILED','VERIFIED','ROLLED_BACK','SUPERSEDED')),
 expires_at timestamptz, created_at timestamptz not null default now(),
 unique(run_id, proposal_hash), unique(run_id, proposal_revision)
);
create index if not exists ix_action_proposal_run_status on aiops.action_proposals(run_id,status,created_at desc);
create table if not exists aiops.approval_records (
 approval_id text primary key, proposal_id text not null references aiops.action_proposals(proposal_id),
 proposal_hash text not null, actor_id text not null, actor_role text not null,
 decision text not null check (decision in ('APPROVE','REJECT','REVOKE')),
 scope jsonb not null default '{}'::jsonb, nonce text not null unique,
 decided_at timestamptz not null default now(), expires_at timestamptz not null,
 audit jsonb not null default '{}'::jsonb
);
create index if not exists ix_approval_proposal_time on aiops.approval_records(proposal_id,decided_at desc);
create table if not exists aiops.effect_receipts (
 effect_id text primary key, proposal_id text not null references aiops.action_proposals(proposal_id),
 approval_id text references aiops.approval_records(approval_id), idempotency_key text not null unique,
 executor_id text not null, adapter_version text not null, started_at timestamptz not null default now(),
 completed_at timestamptz, outcome text not null check (outcome in ('STARTED','SUCCEEDED','FAILED','PARTIAL','UNKNOWN','CANCELLED')),
 result jsonb not null default '{}'::jsonb, error_code text
);
create index if not exists ix_effect_proposal on aiops.effect_receipts(proposal_id,started_at desc);
create table if not exists aiops.verification_records (
 verification_id text primary key, proposal_id text not null references aiops.action_proposals(proposal_id),
 effect_id text references aiops.effect_receipts(effect_id),
 outcome text not null check (outcome in ('PASS','FAIL','PARTIAL','UNKNOWN')),
 expected jsonb not null, observed jsonb not null, evidence_ids jsonb not null default '[]'::jsonb,
 verifier_version text not null, verified_at timestamptz not null default now(), residual_risk jsonb not null default '{}'::jsonb
);
create index if not exists ix_verification_proposal on aiops.verification_records(proposal_id,verified_at desc);
create table if not exists aiops.reconciliation_records (
 reconciliation_id text primary key, run_id text not null references aiops.runs(run_id),
 proposal_id text references aiops.action_proposals(proposal_id), desired_state jsonb not null, observed_state jsonb not null,
 outcome text not null check (outcome in ('CONVERGED','DIVERGED','UNKNOWN','COMPENSATION_REQUIRED')),
 discrepancy jsonb not null default '{}'::jsonb, evidence_ids jsonb not null default '[]'::jsonb,
 created_at timestamptz not null default now()
);
create index if not exists ix_reconciliation_run on aiops.reconciliation_records(run_id,created_at desc);
create table if not exists aiops.learning_cases (
 learning_case_id text primary key, idempotency_key text not null unique, source_run_id text not null references aiops.runs(run_id),
 parent_case_id text references aiops.learning_cases(learning_case_id), revision integer not null check (revision >= 1),
 case_type text not null check (case_type in ('INCIDENT','PROBLEM','CHANGE','REMEDIATION','FALSE_POSITIVE','NEAR_MISS')),
 synthetic boolean not null default true, human_reviewed boolean not null default false, outcome_verified boolean not null default false,
 gold_eligible boolean not null default false, label jsonb not null default '{}'::jsonb,
 evidence_ids jsonb not null default '[]'::jsonb, analysis_id text references aiops.analysis_records(analysis_id),
 critique_id text references aiops.critique_records(critique_id), verification_id text references aiops.verification_records(verification_id),
 exclusion_reasons jsonb not null default '[]'::jsonb, created_at timestamptz not null default now(), reviewed_at timestamptz, reviewed_by text, review_note text,
 unique(source_run_id,revision),
 check (not gold_eligible or (human_reviewed and outcome_verified and not synthetic))
);
create index if not exists ix_learning_eligibility on aiops.learning_cases(gold_eligible,human_reviewed,outcome_verified);
create table if not exists aiops.model_evaluation_runs (
 evaluation_id text primary key, dataset_version text not null, dataset_hash text not null,
 provider text not null, model text not null, prompt_version text not null, policy_version text not null,
 retrieval_version text not null, sample_count integer not null check (sample_count >= 0),
 metrics jsonb not null default '{}'::jsonb,
 gate_decision text not null check (gate_decision in ('PASS','FAIL','INCONCLUSIVE')),
 artifact_uri text, created_at timestamptz not null default now()
);
create or replace function aiops.reject_immutable_mutation() returns trigger language plpgsql as $$
begin raise exception 'immutable ledger: % on %.% is forbidden', TG_OP, TG_TABLE_SCHEMA, TG_TABLE_NAME; end;
$$;
do $$
declare t text;
begin
 foreach t in array array['analysis_records','critique_records','policy_decisions','approval_records','verification_records','reconciliation_records','model_evaluation_runs'] loop
  execute format('drop trigger if exists %I on aiops.%I', 'trg_immutable_'||t, t);
  execute format('create trigger %I before update or delete on aiops.%I for each row execute function aiops.reject_immutable_mutation()', 'trg_immutable_'||t, t);
 end loop;
end $$;
create or replace function aiops.guard_gold_learning_case() returns trigger language plpgsql as $$
begin
 if NEW.gold_eligible and (NEW.synthetic or not NEW.human_reviewed or not NEW.outcome_verified) then
  raise exception 'gold learning eligibility requires non-synthetic, human-reviewed, outcome-verified case';
 end if;
 return NEW;
end;
$$;
drop trigger if exists trg_guard_gold_learning_case on aiops.learning_cases;
create trigger trg_guard_gold_learning_case before insert or update on aiops.learning_cases for each row execute function aiops.guard_gold_learning_case();
