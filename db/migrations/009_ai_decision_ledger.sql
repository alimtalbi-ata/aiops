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
 status text not null check (status in ('PROPOSED','REJECTED','APPROVED','EXPIRED','EXECUTING','EXECUTED','FAILED','VERIFIED','ROLLED_BACK','SUPERSEDED','REVOKED')),
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
 approval_id text not null references aiops.approval_records(approval_id), idempotency_key text not null unique,
 executor_id text not null, adapter_version text not null, started_at timestamptz not null default now(),
 completed_at timestamptz, outcome text not null check (outcome in ('STARTED','SUCCEEDED','FAILED','PARTIAL','UNKNOWN','CANCELLED')),
 result jsonb not null default '{}'::jsonb, error_code text
);
create index if not exists ix_effect_proposal on aiops.effect_receipts(proposal_id,started_at desc);
create table if not exists aiops.verification_records (
 verification_id text primary key, proposal_id text not null references aiops.action_proposals(proposal_id),
 effect_id text not null references aiops.effect_receipts(effect_id),
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
 check (not human_reviewed or (reviewed_by is not null and btrim(reviewed_by)<>'' and review_note is not null and btrim(review_note)<>'' and reviewed_at is not null)),
 check (not gold_eligible or (human_reviewed and outcome_verified and not synthetic and reviewed_by is not null and review_note is not null and reviewed_at is not null))
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
declare run_mode text; evidence_count integer; evidence_is_synthetic boolean;
begin
 select mode into run_mode from aiops.runs where run_id=NEW.source_run_id;
 if not found then raise exception 'learning case source run does not exist'; end if;
 if jsonb_typeof(NEW.evidence_ids)<>'array' then raise exception 'learning evidence IDs must be an array'; end if;
 if jsonb_array_length(NEW.evidence_ids)=0 then raise exception 'learning case requires evidence IDs'; end if;
 select count(*) into evidence_count from jsonb_array_elements_text(NEW.evidence_ids) e(id) join aiops.evidence ev on ev.evidence_id=e.id;
 if evidence_count<>jsonb_array_length(NEW.evidence_ids) then raise exception 'learning case references unknown evidence'; end if;
 select exists(
  select 1 from jsonb_array_elements_text(NEW.evidence_ids) e(id)
  join aiops.evidence ev on ev.evidence_id=e.id
  where coalesce(ev.provenance->>'synthetic','unknown')<>'false'
 ) into evidence_is_synthetic;
 NEW.synthetic := (run_mode<>'LIVE') or evidence_is_synthetic;
 if NEW.human_reviewed and (NEW.reviewed_by is null or btrim(NEW.reviewed_by)='' or NEW.review_note is null or btrim(NEW.review_note)='' or NEW.reviewed_at is null) then
  raise exception 'human review requires reviewer identity, rationale and timestamp';
 end if;
 if NEW.outcome_verified then
  if NEW.verification_id is null or not exists(
   select 1 from aiops.verification_records v
   join aiops.action_proposals p on p.proposal_id=v.proposal_id
   where v.verification_id=NEW.verification_id and v.outcome='PASS' and p.run_id=NEW.source_run_id
  ) then raise exception 'verified learning outcome requires a passed verification for the same run'; end if;
 end if;
 if NEW.analysis_id is not null and not exists(select 1 from aiops.analysis_records where analysis_id=NEW.analysis_id and run_id=NEW.source_run_id) then
  raise exception 'learning analysis must belong to the source run';
 end if;
 if NEW.critique_id is not null and not exists(select 1 from aiops.critique_records where critique_id=NEW.critique_id and run_id=NEW.source_run_id) then
  raise exception 'learning critique must belong to the source run';
 end if;
 if NEW.gold_eligible and (NEW.synthetic or not NEW.human_reviewed or not NEW.outcome_verified) then
  raise exception 'gold learning eligibility requires non-synthetic, human-reviewed, outcome-verified case';
 end if;
 return NEW;
end;
$$;
drop trigger if exists trg_guard_gold_learning_case on aiops.learning_cases;
create trigger trg_guard_gold_learning_case before insert or update on aiops.learning_cases for each row execute function aiops.guard_gold_learning_case();

-- A proposal's identity and hash are immutable; only its lifecycle status may advance.
create or replace function aiops.guard_action_proposal_transition() returns trigger language plpgsql as $$
declare approval_count integer; approved_roles text[];
begin
 if NEW.run_id is distinct from OLD.run_id
 or NEW.analysis_id is distinct from OLD.analysis_id
 or NEW.critique_id is distinct from OLD.critique_id
 or NEW.source_action_id is distinct from OLD.source_action_id
 or NEW.proposal_revision is distinct from OLD.proposal_revision
 or NEW.target_ci_id is distinct from OLD.target_ci_id
 or NEW.action_type is distinct from OLD.action_type
 or NEW.risk_tier is distinct from OLD.risk_tier
 or NEW.parameters is distinct from OLD.parameters
 or NEW.evidence_ids is distinct from OLD.evidence_ids
 or NEW.preconditions is distinct from OLD.preconditions
 or NEW.expected_postconditions is distinct from OLD.expected_postconditions
 or NEW.rollback_plan is distinct from OLD.rollback_plan
 or NEW.proposal_hash is distinct from OLD.proposal_hash
 or NEW.expires_at is distinct from OLD.expires_at
 or NEW.created_at is distinct from OLD.created_at then
  raise exception 'proposal identity and hash are immutable';
 end if;
 if NEW.status is not distinct from OLD.status then return NEW; end if;
 if not (
  (OLD.status='PROPOSED' and NEW.status in ('APPROVED','REJECTED','EXPIRED','SUPERSEDED')) or
  (OLD.status='APPROVED' and NEW.status in ('EXECUTING','EXPIRED','SUPERSEDED','REVOKED')) or
  (OLD.status='EXECUTING' and NEW.status in ('EXECUTED','FAILED')) or
  (OLD.status='EXECUTED' and NEW.status in ('VERIFIED','ROLLED_BACK','FAILED')) or
  (OLD.status='FAILED' and NEW.status in ('ROLLED_BACK','SUPERSEDED'))
 ) then
  raise exception 'invalid proposal lifecycle transition: % -> %', OLD.status, NEW.status;
 end if;
 if NEW.status in ('APPROVED','EXECUTING','EXECUTED','VERIFIED') then
  if not exists(select 1 from aiops.runs r where r.run_id=NEW.run_id and r.mode='LIVE') then
   raise exception 'real action lifecycle requires LIVE run';
  end if;
 end if;
 if NEW.status='APPROVED' then
  if not exists(select 1 from aiops.approval_records a where a.proposal_id=NEW.proposal_id and a.proposal_hash=NEW.proposal_hash and a.decision='APPROVE' and a.expires_at>now() and a.scope->>'target_ci_id'=NEW.target_ci_id and a.scope->>'action_type'=NEW.action_type) then
   raise exception 'approval record bound to exact proposal hash and scope is required';
  end if;
  if NEW.risk_tier='CRITICAL' then
   select count(distinct actor_id), array_agg(distinct actor_role) into approval_count,approved_roles
   from aiops.approval_records where proposal_id=NEW.proposal_id and proposal_hash=NEW.proposal_hash and decision='APPROVE' and expires_at>now();
   if coalesce(approval_count,0)<2 or not (coalesce(approved_roles,'{}') @> array['security_admin','incident_commander']) then
    raise exception 'critical proposal requires security_admin and incident_commander approvals';
   end if;
  end if;
 end if;
 if NEW.status='REJECTED' and not exists(select 1 from aiops.approval_records a where a.proposal_id=NEW.proposal_id and a.proposal_hash=NEW.proposal_hash and a.decision='REJECT') then
  raise exception 'rejection requires a recorded human decision';
 end if;
 return NEW;
end;
$$;
drop trigger if exists trg_guard_action_proposal_transition on aiops.action_proposals;
create trigger trg_guard_action_proposal_transition before update on aiops.action_proposals for each row execute function aiops.guard_action_proposal_transition();

create or replace function aiops.guard_action_proposal_insert() returns trigger language plpgsql as $$
declare a record; q record; action_record jsonb; evidence_count integer;
begin
 select output,evidence_ids,status into a from aiops.analysis_records where analysis_id=NEW.analysis_id and run_id=NEW.run_id;
 if not found or a.status<>'VALID' then raise exception 'proposal requires a valid analysis for the same run'; end if;
 select output,evidence_ids,validated into q from aiops.critique_records where critique_id=NEW.critique_id and analysis_id=NEW.analysis_id and run_id=NEW.run_id;
 if not found or q.validated is not true or coalesce(q.output->'issues','[]'::jsonb)<>'[]'::jsonb or coalesce(q.output->'unsafe_actions','[]'::jsonb)<>'[]'::jsonb or exists(select 1 from jsonb_array_elements(coalesce(q.output->'claim_checks','[]'::jsonb)) checks(value) where coalesce((value->>'supported')::boolean,false) is not true) then
  raise exception 'proposal requires a clean validated critique for the same analysis';
 end if;
 select value into action_record from jsonb_array_elements(coalesce(a.output->'recommended_actions','[]'::jsonb)) where value->>'action_id'=NEW.source_action_id limit 1;
 if action_record is null then raise exception 'source action is not present in validated analysis'; end if;
 if action_record->>'risk_tier' is distinct from NEW.risk_tier
 or coalesce((action_record->>'advisory_only')::boolean,false) is not true
 or coalesce((action_record->>'requires_human_approval')::boolean,false) is not true
 or (action_record->>'target_ci_id' is not null and action_record->>'target_ci_id'<>NEW.target_ci_id) then
  raise exception 'proposal differs from advisory-only analyst action';
 end if;
 if jsonb_typeof(NEW.evidence_ids)<>'array' then raise exception 'proposal evidence IDs must be an array'; end if;
 if jsonb_array_length(NEW.evidence_ids)=0 then raise exception 'proposal evidence IDs must be non-empty'; end if;
 if not (a.evidence_ids @> NEW.evidence_ids) or not (q.evidence_ids @> NEW.evidence_ids) then raise exception 'proposal evidence must be a subset of analysis and critique evidence'; end if;
 select count(*) into evidence_count from jsonb_array_elements_text(NEW.evidence_ids) e(id) join aiops.evidence ev on ev.evidence_id=e.id;
 if evidence_count<>jsonb_array_length(NEW.evidence_ids) then raise exception 'proposal references unknown evidence'; end if;
 if jsonb_typeof(NEW.preconditions)<>'array' or jsonb_typeof(NEW.expected_postconditions)<>'array' then raise exception 'proposal preconditions and postconditions must be arrays'; end if;
 if jsonb_array_length(NEW.preconditions)=0 or jsonb_array_length(NEW.expected_postconditions)=0 then raise exception 'proposal requires preconditions and measurable postconditions'; end if;
 if NEW.risk_tier in ('HIGH','CRITICAL') and (NEW.rollback_plan='{}'::jsonb or NEW.rollback_plan='null'::jsonb) then
  raise exception 'high-risk proposal requires rollback plan';
 end if;
 return NEW;
end;
$$;
drop trigger if exists trg_guard_action_proposal_insert on aiops.action_proposals;
create trigger trg_guard_action_proposal_insert before insert on aiops.action_proposals for each row execute function aiops.guard_action_proposal_insert();

-- An effect receipt is evidence of an actual adapter invocation, not an approval or proposal.
create or replace function aiops.guard_effect_receipt() returns trigger language plpgsql as $$
declare p record; a record; approval_count integer; approved_roles text[];
begin
 if TG_OP='DELETE' then raise exception 'effect receipts cannot be deleted'; end if;
 if TG_OP='UPDATE' then
  if NEW.proposal_id is distinct from OLD.proposal_id or NEW.approval_id is distinct from OLD.approval_id or NEW.idempotency_key is distinct from OLD.idempotency_key or NEW.executor_id is distinct from OLD.executor_id or NEW.adapter_version is distinct from OLD.adapter_version or NEW.started_at is distinct from OLD.started_at then
   raise exception 'effect receipt identity is immutable';
  end if;
  if OLD.outcome<>'STARTED' or NEW.outcome not in ('SUCCEEDED','FAILED','PARTIAL','UNKNOWN','CANCELLED') then
   raise exception 'invalid effect receipt outcome transition: % -> %',OLD.outcome,NEW.outcome;
  end if;
  if NEW.completed_at is null then NEW.completed_at=now(); end if;
  return NEW;
 end if;
 select ap.*,r.mode into p from aiops.action_proposals ap join aiops.runs r on r.run_id=ap.run_id where ap.proposal_id=NEW.proposal_id;
 if not found or p.mode<>'LIVE' or p.status<>'APPROVED' then raise exception 'effect requires an approved proposal in LIVE mode'; end if;
 select * into a from aiops.approval_records where approval_id=NEW.approval_id;
 if not found or a.proposal_id<>NEW.proposal_id or a.proposal_hash<>p.proposal_hash or a.decision<>'APPROVE' or a.expires_at<=now() then
  raise exception 'effect requires an active approval bound to the proposal hash';
 end if;
 if a.scope->>'target_ci_id'<>p.target_ci_id or a.scope->>'action_type'<>p.action_type then raise exception 'approval scope mismatch'; end if;
 if p.risk_tier='CRITICAL' then
  select count(distinct actor_id),array_agg(distinct actor_role) into approval_count,approved_roles
  from aiops.approval_records where proposal_id=NEW.proposal_id and proposal_hash=p.proposal_hash and decision='APPROVE' and expires_at>now();
  if coalesce(approval_count,0)<2 or not (coalesce(approved_roles,'{}') @> array['security_admin','incident_commander']) then
   raise exception 'critical effect requires two-role approval';
  end if;
 end if;
 if NEW.outcome<>'STARTED' then raise exception 'effect receipt must start in STARTED state'; end if;
 return NEW;
end;
$$;
drop trigger if exists trg_guard_effect_receipt on aiops.effect_receipts;
create trigger trg_guard_effect_receipt before insert or update on aiops.effect_receipts for each row execute function aiops.guard_effect_receipt();

create or replace function aiops.guard_verification_record() returns trigger language plpgsql as $$
declare effect_proposal text; effect_outcome text;
begin
 select proposal_id,outcome into effect_proposal,effect_outcome from aiops.effect_receipts where effect_id=NEW.effect_id;
 if not found or effect_proposal<>NEW.proposal_id then raise exception 'verification must reference effect for the same proposal'; end if;
 if effect_outcome not in ('SUCCEEDED','FAILED','PARTIAL','UNKNOWN') then raise exception 'effect must be terminal before verification'; end if;
 if jsonb_typeof(NEW.evidence_ids)<>'array' then raise exception 'verification evidence IDs must be an array'; end if;
 if jsonb_array_length(NEW.evidence_ids)=0 then raise exception 'verification requires independent evidence IDs'; end if;
 if (select count(*) from jsonb_array_elements_text(NEW.evidence_ids) e(id) join aiops.evidence ev on ev.evidence_id=e.id)<>jsonb_array_length(NEW.evidence_ids) then raise exception 'verification references unknown evidence'; end if;
 return NEW;
end;
$$;
drop trigger if exists trg_guard_verification_record on aiops.verification_records;
create trigger trg_guard_verification_record before insert on aiops.verification_records for each row execute function aiops.guard_verification_record();

create or replace function aiops.guard_reconciliation_record() returns trigger language plpgsql as $$
begin
 if NEW.proposal_id is not null and not exists(select 1 from aiops.action_proposals where proposal_id=NEW.proposal_id and run_id=NEW.run_id) then
  raise exception 'reconciliation proposal must belong to the same run';
 end if;
 if jsonb_typeof(NEW.evidence_ids)<>'array' then raise exception 'reconciliation evidence IDs must be an array'; end if;
 if jsonb_array_length(NEW.evidence_ids)=0 then raise exception 'reconciliation requires evidence IDs'; end if;
 if (select count(*) from jsonb_array_elements_text(NEW.evidence_ids) e(id) join aiops.evidence ev on ev.evidence_id=e.id)<>jsonb_array_length(NEW.evidence_ids) then raise exception 'reconciliation references unknown evidence'; end if;
 return NEW;
end;
$$;
drop trigger if exists trg_guard_reconciliation_record on aiops.reconciliation_records;
create trigger trg_guard_reconciliation_record before insert on aiops.reconciliation_records for each row execute function aiops.guard_reconciliation_record();

drop trigger if exists trg_immutable_delete_action_proposals on aiops.action_proposals;
create trigger trg_immutable_delete_action_proposals before delete on aiops.action_proposals for each row execute function aiops.reject_immutable_mutation();
drop trigger if exists trg_immutable_delete_effect_receipts on aiops.effect_receipts;
create trigger trg_immutable_delete_effect_receipts before delete on aiops.effect_receipts for each row execute function aiops.reject_immutable_mutation();
