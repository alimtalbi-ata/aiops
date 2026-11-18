# INT09B final offline convergence
Reuse C e4e6e73cefeca7ad278912fbd2920464c0d0df12 tests/test_int09c_golden_final.py exact blob 65018b58be2b3a02bfa31db0b974f5c6ad2fceb3. No new validator. Existing B admission and preterminal fixture used directly. Final history prefix is synthetic, not durable inclusion proof. No transactional terminal callback authorized.

db/migrations/015_core_run_event_idempotency.sql 8090ae787400e6a6f87f763b6af9ad2f4287f422
ALTER TABLE aiops.run_events ADD COLUMN IF NOT EXISTS event_key text;
CREATE UNIQUE INDEX IF NOT EXISTS ux_run_events_event_key

db/migrations/016_acme_sandbox_attempts.sql 848c6a3a163f227adac17a153e3388e622b989ba
create table if not exists aiops.acme_sandbox_attempts (
 incident_id text not null unique references aiops.incidents(incident_id),
 run_id text not null unique references aiops.runs(run_id),
 ticket_id text not null unique check (ticket_id like 'SIM-GLPI-%'),
 proposal_id text not null unique check (proposal_id like 'PROP-SIM-%'),
 analysis_id text not null unique references aiops.analysis_records(analysis_id),
 critique_id text not null unique references aiops.critique_records(critique_id),
drop trigger if exists trg_acme_sandbox_immutable on aiops.acme_sandbox_attempts;
create trigger trg_acme_sandbox_immutable before update or delete

Epoch audit: historical C reference wire a50687e8f9fbbe601a770c12b21cdfc15b236174, notification 81068f4d55196fdc2c0896967475d84b670856c4. Explicit epoch occurrences: 0, 0. No epoch inferred from attempts or token. Central arbitration required if no existing source found. Terminal callback remains disabled; positive ACME resolve(x) separate from REJECT terminal_reject(tenant_id,event_id,payload). No DDL or runtime.
