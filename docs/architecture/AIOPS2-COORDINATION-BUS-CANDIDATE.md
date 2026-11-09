# AIOps2 — Coordination bus and execution chain (candidate design)

Status: DESIGN CANDIDATE; **not installed, not dispatched, not E2E-qualified**. Extends `docs/architecture/AIOPS2-MULTIAGENT-ORCHESTRATION.md`; does not supersede production safety rules. Primary objective: deliver and demonstrate the FS/SAN → Core → Intelligence/Critic → Twin → Policy/HITL → Worker/Temporal → Evidence → Portal/GLPI use case.

## 1. One control plane, multiple execution planes

- **GitHub Issues/PRs**: durable work queue, ownership, approvals, dependencies, discussion. Existing #457–#464 remain canonical; do not create a parallel issue hierarchy.
- **GitHub Actions**: event-driven validation, schema checking, queue reconciliation and CI on exact SHAs. Workflow execution is *not* proof that Codex ran, nor proof that Debian deployed.
- **Five existing ChatGPT schedules**: Integration H:00 (conductor/reconciler), Core H:12, Worker H:24, Twin H:36, Portal H:48 (domain supervisors). They consume the same event stream and create/update work items; they do not claim to be Codex sessions. Retain their existing schedules initially.
- **Eight Codex executors**: identities/permissions/transport must be discovered and recorded individually, not assumed from the number of issues. Codex Cloud handles isolated source tasks where a verified connector is available; Codex CLI on SRV-DEB-05 handles approved Debian qualification through the existing poller/cron. No assumed Cloud↔CLI transport.
- **Debian existing cron/poll.sh/reporter/publisher**: discover actual input protocol and directionality before enabling dispatch. Preserve five Compose stacks, customer data, HITL and Policy.
- **ChatGPT Labs/Work**: optional interactive investigation, architecture decisions, visualization and human review. Not a durable queue or unverified autonomous executor.

## 2. Message bus: use GitHub as durable event log, not chat comments as a transport guarantee

Proposed additive logical envelope (JSON schema to implement and test in phase 1):
```json
{
  "schema_version": "1.0",
  "message_id": "uuid",
  "correlation_id": "FS1250-demo-001",
  "causation_id": null,
  "work_id": "457/core/fs-event-contract",
  "kind": "TASK_REQUEST",
  "producer": "schedule.integration",
  "target": "codex.core",
  "created_at": "ISO8601-UTC",
  "expires_at": "ISO8601-UTC",
  "idempotency_key": "work_id:revision:target",
  "revision": 1,
  "source": {"repo": "alimtalbi-ata/aiops", "ref": "full-sha"},
  "depends_on": [],
  "payload_ref": "github-issue-or-artifact-url",
  "evidence_refs": [],
  "requires_approval": false
}
```
Kinds: `TASK_REQUEST`, `TASK_ACCEPTED`, `HEARTBEAT`, `BLOCKED`, `ARTIFACT_READY`, `TEST_RESULT`, `DEPLOY_CANDIDATE`, `RUNTIME_RECEIPT`, `E2E_RESULT`, `APPROVAL_REQUIRED`, `TASK_DONE`, `TASK_FAILED`, `TASK_CANCELLED`. Each message carries immutable ID, UTC timestamp, correlation and causation IDs, source revision and evidence pointers. Store events in a GitHub-managed append-only artifact/log with one-writer or optimistic concurrency; issue comments are the readable projection, not a reliable queue. No secrets or large logs in the envelope. Do not commit per-minute telemetry to main.

**Transport adapters:** GitHub Actions webhook/event → normalized queue; Codex Cloud adapter (only after API/connector dispatch verified); existing Debian poller adapter (only after input contract and auth verified); GitHub status/PR adapter; Debian publisher adapter. Each adapter emits acceptance and completion receipts; absent receipt means `DISPATCH_NOT_VERIFIED`, not `RUNNING`.

## 3. Work-item lifecycle and reliability

`PROPOSED → READY → CLAIMED → RUNNING → ARTIFACT_READY → VERIFIED → INTEGRATED → DEMONSTRATED → DONE`.
Exceptions: `BLOCKED`, `WAITING_APPROVAL`, `TIMED_OUT`, `FAILED`, `CANCELLED`.
A claim is a lease with owner, session ID, acquired UTC and expiry. Heartbeat renews it. Expiry returns to READY only after reconciling external job state to avoid duplicate executions. At-least-once event delivery, idempotent handlers, compare-and-swap revisions and deduplication by `idempotency_key`; do not promise exactly-once effects. Retry with bounded backoff; poison messages to a visible dead-letter queue. No automatic retry of irreversible operations. Manual recovery from uncertain external effects.

An agent's output must include actual execution session/job ID (or `UNVERIFIED`), full SHA, changed files, exact test command and exit code, CI run URL, artifacts, dependency status, next consumer, rollback and freshness. Claims such as “tests written” never count as `TEST_RESULT`.

## 4. Dependency graph and handoff

```text
Event fixture / sensor
  → Core event & incident contract
  → Intelligence / Critic analysis
  → Twin scenario / impact
  → Policy + HITL decision (hard safety gate)
  → Temporal / Worker action (authorized isolated target)
  → Evidence chain
  → Portal read-only rendering
  → GLPI authenticated readback (isolated, authorized)
  → E2E receipt
```
Parallelize independent code work but integrate by interface dependencies. Integration conductor assigns one *critical-path blocker* at a time and issues `TASK_REQUEST` only to a verified executor. A producer emits `ARTIFACT_READY`; the consumer acknowledges `TASK_ACCEPTED` and validates the contract; on mismatch emits `BLOCKED` referencing producer SHA. No silent success or ambiguous ownership.

## 5. The five schedules are a control loop, not a queue

- Integration: every cycle reconcile GitHub queue, Cloud sessions, Debian receipts, CI, stale leases and dependencies; choose critical path; issue only actionable tasks; publish one concise progress summary with verified proof.
- Core: supervise Core contracts and producer-consumer handoffs; execute only through verified Codex adapter.
- Worker: supervise Intelligence/Critic, Temporal, HITL and Evidence boundaries.
- Twin: supervise isolated impact/negative tests; never touch live targets.
- Portal: supervise portal rendering and GLPI readback contracts; no unauthorized writes.
- Eight Codex executor slots are separate from these five roles. Map each slot to a real execution identity, permissions and source of receipt; unknown slots remain `NOT_CONNECTED`, not invented “active agents”.

## 6. Gates: CI ≠ deployment ≠ E2E

G0 exact SHA tests and security checks; G1 candidate provenance (source SHA → build digest → Compose service) and fresh Debian receipt; G2 isolated integration, fail-closed Policy/HITL and authorized GLPI readback; G3 reproducible full use case with evidence per hop; G4 installation and rollback readiness. A passing synthetic fixture may qualify only synthetic coverage. `latest-usecase.json` must be emitted by a real qualification job, never fabricated by the publisher.

## 7. Execution sequence — minimum viable coordination bus

**Phase A, discover before creating**: inspect existing GitHub Actions workflows, cron/poll.sh, publisher, issue→Codex routing, Cloud execution API and all eight agent identities. Produce a single matrix: trigger, transport, identity, acknowledgement, result, failure handling, proof URL. No new dispatcher until a specific missing edge is proven.

**Phase B, close one real round trip**: submit one harmless read-only task with correlation ID through the existing channel; capture `TASK_ACCEPTED`, session ID, heartbeat, `TASK_DONE`, Debian receipt and linked GitHub issue. If no ack, classify the exact failed edge; do not widen scope.

**Phase C, build only missing primitives**: versioned message schema, one queue reconciler, one verified adapter, idempotency/lease and event projections, GitHub Actions contract checks. Prefer existing workflow/reporter/publisher; no duplicate crons. Validate concurrent claims and redelivery.

**Phase D, deliver use case**: execute the real dependency DAG with verified agents; run exact-SHA CI, isolated integration, authenticated GLPI readback where authorized, Debian E2E receipts and portal trace. Fix first critical-path failure until G3 is true.

**Phase E, scale**: enable remaining verified Cloud/CLI adapters, alerts on stalled leases and stale receipts, latency and throughput dashboards. Do not scale seven disconnected agents.

## 8. Operational SLOs and controls

Suggested initial thresholds (to calibrate from observed cadence): acknowledgement ≤ one existing poll cycle + 2 minutes; heartbeat age ≤ 2 poll cycles; reporter freshness ≤ 3 minutes; stuck work escalated to Integration on next H:00 cycle. Track lead time from request to qualified E2E, count of verified Codex sessions, acceptance rate, integration pass rate, critical path age and unowned blocked tasks. Metrics must distinguish missing telemetry from zero failures.

Permissions: least-privilege GitHub tokens; protected branch/PR gate; signed or otherwise verifiable provenance where available; secrets excluded from events; no executable arbitrary issue-comment text. The dispatcher must accept allowlisted task kinds and validated payloads only. Production GLPI/PG, Compose, cron and irreversible changes require explicit scoped approval and preflight. No automatic merge/deploy on unverified evidence.

## 9. Acceptance criteria for the orchestration system

1. A single task is traceable request → accepted Codex session → commit → exact-SHA CI → Debian receipt → E2E result.
2. A dead executor produces visible timeout and safe requeue without double action.
3. Two agents cannot own the same lease or overwrite another role's worktree.
4. A stale/contradictory receipt fails closed.
5. Policy/HITL denial is enforced and auditable.
6. The end-to-end demo is replayable with step-by-step evidence; no synthetic-to-real promotion.
7. The five ChatGPT schedules consume the same state, do not duplicate commands or report unverified Codex activity.

**Explicitly unresolved:** whether GitHub→Codex Cloud dispatch is available; whether Debian cron polls an inbound command queue or only publishes reports; exact identities of Codex slots 1–7; GitHub Actions permissions and runner topology. These are integration discovery tasks, not assumptions.
