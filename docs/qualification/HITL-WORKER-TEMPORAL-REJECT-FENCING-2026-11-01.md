# Policy/HITL P0 — Core-fenced REJECT notification contract (2026-11-01)

Status: **DRAFT / NO_GO**. Source base: sole architect candidate #234 at
`d5227f5c3981a53dd2a42d5384dce798cfaf0d33`; main
`ae7c3e5102b99a66bd7806d602146f1309a9749d`.
Source-only: #204 on #194. #239 and #243 are already architect-integrated:
**do not cherry-pick or re-port them**.

## Scope and authority

Only `app/worker/hitl_reject_notification.py`, its tests, this document,
and a dedicated CI workflow. No `app/core/main.py`, migrations, Policy HTTP,
shared Quality, Portal, executor, deployment or release changes.

Core remains sole owner of proposal hash/revision, tenant/run, decision,
lease expiry/ownership/fencing and durable ACK. The currently installed
`011_hitl_decision_outbox.sql` is an outbox storage schema, **not** proof
that a Core HTTP claim/ACK contract is present on the candidate.

Worker's pure adapter accepts a Core-owned claim snapshot **only if**
it carries exact tenant/run/proposal/hash/revision/lease owner/token,
`REJECT/REJECTED|REVOKED` and explicit false effect flags. It emits
a notification-only Temporal payload without lease token and never
handles APPROVE. It ACKs only after signal success, and accepts an ACK
only with the exact original immutable binding, `DELIVERED`,
boolean `idempotent` and both effect flags false. The ACK result is
not an authorization. An exception before ACK leaves the lease for Core
to reclaim. No claim/ACK HTTP wiring is enabled until Core agrees.

## Core/architect contract request (blocking)

Core to define and test in its own scope:

1. `POST /api/hitl/decision-outbox/claim`: authenticated Worker service,
   tenant scope, `owner`, bounded `limit`/`lease_seconds`; response
   `items` with `event_id,tenant_id,run_id,proposal_id,proposal_hash,
   proposal_revision,decision,source_status,lease_owner,lease_token`,
   plus explicit `execution_allowed=false/effect_allowed=false`
   on envelope and items. Core validates immutable proposal and
   actor/decision record and uses row-lock lease fencing.
2. `POST /api/hitl/decision-outbox/{event_id}/delivered`: same Worker
   service, tenant/run/proposal/hash/revision/owner/lease_token,
   Core validates token expiry and current lease owner **in one
   transaction**, ACK idempotency after commit, and returns the exact
   binding with `DELIVERED`, boolean `idempotent`, false effect flags.
   Wrong tenant, token, hash, revision or event must be refused.
3. Explicit status/error semantics for stale lease, duplicate,
   signal accepted but ACK response lost, retry budget/dead-letter.
   **Actual network ACK loss remains NOT_TESTED**; an injected exception
   after fake commit is only a simulation.
4. Signal consumer must match immutable tenant/run/proposal/hash/revision
   to Core ledger before *any* transition. Temporal history is not a
   business ledger; no signal grants approval or effect. Real OIDC
   identity remains **NOT_ATTESTED**.

## Evidence and labels

- Pure Worker contract unit tests: fail-closed mismatch, REJECT only,
  no-effect, signal-before-ACK, duplicate and injected lost response.
  `OBSERVED_CI_UNIT` only.
- Dedicated disposable Temporal SDK dev server: real Worker shutdown,
  new Worker replay and two synthetic REJECT signals to a test-only
  notification sink. This is **not** the production `IncidentWorkflow`
  or a real Core claim/ACK endpoint.
- Existing #234 PG16/DR model (migrations 001/004/009/010/011/012)
  is rerun by the dedicated CI job on this PR head with
  `pg_dump/pg_restore` major 16, without modifying SQL or DR code.
- Real Core claim/ACK HTTP, network ACK loss, Temporal server restart,
  production IncidentWorkflow, actual OIDC/MFA: **NOT_TESTED** or
  **NOT_ATTESTED** as applicable. No effect receipts, human approval,
  LIVE or external GLPI writes.

## Commands and rollback

```bash
PYTHONPATH=app python -m unittest discover -s tests -p 'test_worker_hitl_reject_notification.py' -v
# CI-only, disposable PostgreSQL service with AIOPS_CI_OUTBOX_DISPOSABLE=YES:
python -m unittest discover -s tests -p 'test_hitl_pg16_candidate_outbox.py' -v
pg_dump --version; pg_restore --version # require 16.x
```

Rollback: close draft PR or revert its four scoped files; no database
migration, persistent data, shared workflow or Worker runtime poller
is modified. CI service databases and Temporal dev server are ephemeral.
Integration remains architect-only, `RELEASE_STABLE=NO_GO`.
