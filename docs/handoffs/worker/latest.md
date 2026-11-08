# Worker #459 — incremental offline safety regression handoff

UTC: 2026-11-08T17:00:32+00:00
Issue: https://github.com/alimtalbi-ata/aiops/issues/459
Role: Worker
Branch: agent/worker/459-pipeline
Exact test implementation SHA: 97bb87fb7c9d66c540db51a0428ce52f1eadf9a1
Source base: adcceb74bfd6289c161e344382e19be7952e3859 (orchestration candidate).
Changed paths: tests/test_worker_pipeline_safety.py; docs/handoffs/worker/latest.md.
Interfaces touched: NONE. No application source, Core/Twin/Portal/Integration, cron or Compose changes.

## Current result

User requested continuation after the initial blocked report. Added independently executable Worker safety regressions without editing the active #446 Worker entrypoint or copying the root-level FS147 pipeline. Runtime changes still require ownership/base arbitration.

Five tests execute existing activity/workflow bodies selected from app/worker/main.py using AST. Decorators/imports/startup are excluded; service calls and Temporal activity scheduling use test doubles. Covers invalid modes before service effects; LIVE refusal before Evidence/Twin/Policy calls across seven stages; Policy BLOCKED/UNKNOWN/FAIL with no completed event/checkpoint; repeated activities retaining event/command keys while attempt metadata changes; Critic/Policy BLOCKED workflow results preventing HITL/REMEDIATE/VERIFY/RESOLVE.

This is an incremental test contribution, not a runtime fix or complete issue acceptance. It does not prove SDK integration, actual Temporal history replay, durable duplicate suppression, concurrent delivery, authenticated Critic/Policy behavior or production safety. Stable idempotency keys alone do not establish Core deduplication. Critic coverage here is the workflow boundary's BLOCKED result, not a live Analyst/Critic adapter.

## Commands and results

```
cd /workspace/aiops
python -m unittest discover -s tests -p 'test_worker_pipeline_safety.py' -v
# 5 PASS
python -m unittest discover -s tests -p 'test_simulation_policy_contract.py' -v
# 6 PASS
git diff --check
# PASS
```

Earlier exact candidate 578c46e31fb543a682c710d3502ee18aa005a00e was exported with git archive into /tmp/worker459-validation; `python -m unittest discover -s tests -p 'test_worker_fs147*.py' -v` passed 29 existing tests there. These are distinct source/test targets, not 40 tests on the current branch.

CODE: COMMITTED — tests only; no application behavior changed.
CI: NOT_VERIFIED. Existing workflow does not explicitly select this new test filename; standalone command above is required. No workflow edited under Worker ownership.
DEBIAN: UNKNOWN. No receipt inspected or remote command run.
E2E: NOT_VERIFIED. Actual Temporal replay/restart/concurrency remains UNRUN.

Dependencies: Integration #457 approval of integration base and ownership for any application patch; Core #458 authoritative claim/outbox contracts; api.github.com network access for draft PR/comment and CI queries. Existing GH_TOKEN presence is not a reason to request a replacement token.
Risk: offline source-body execution excludes SDK wiring; no claim of deployment readiness. Unknown/denied states remain fail closed.
Rollback: revert 97bb87fb7c9d66c540db51a0428ce52f1eadf9a1 to remove the test addition; no runtime rollback needed.
Next owner: Integration, review this independent test increment and arrange inclusion in its test command; then Worker, qualify replay/durable dedup on the approved runtime candidate.

## GitHub publication

Git branch pushes work. API attempts return 403 Forbidden; draft PR/comment and exact-SHA CI cannot be confirmed. Proposed PR base: ops/aiops2-multiagent-orchestration-20261108, subject to Integration review; no merge authorized. Earlier onboarding draft reads/save failed INVALID_ARGUMENT, so the api.github.com domain addition is not confirmed persisted. Environment status on continuation shows enforced restricted policy with no api.github.com entry. Add that destination in environment network settings while preserving other destinations, then retry API publication.

## Initial discovery (historical; application edits remain gated)


Read AGENTS.md and orchestration contract on ops/aiops2-multiagent-orchestration-20261108; continuity, component/reuse catalog and cross-branch reuse inventory. Read issues #457/#458/#459 and PRs #446/#450/#456 through public GitHub pages. Git HTTPS fetch works; API GraphQL and REST return proxy HTTP 403 Forbidden. A GH_TOKEN binding is present; no credential values were inspected. This is not evidence that a new token is needed.

Fetched remote branches. Existing FS147 read-only pipeline lives at `worker/fs147_readonly_pipeline.py`, NOT `app/worker/**`. Source candidate branch `worker/fs147-readonly-pipeline-actor-binding-20261106`, exact SHA `578c46e31fb543a682c710d3502ee18aa005a00e`. Reuses atomic/durable claim callback, duplicate suppression, Analyst/Critic/Policy scope and refusal checks, observation checks, and NO_EFFECT output. This is callback orchestration, not qualified durable Temporal replay or authenticated live adapters.

Existing PR #446 remains Draft and explicitly modifies `app/worker/main.py` (execution admission guard). PR #450 owns Core action-bound HITL/fencing and describes unresolved authoritative lease/outbox/crash dedup requirements. Main contains the baseline Temporal worker; the FS147 candidate's app/worker/main.py has no diff from main, while its read-only pipeline is a separate root-level module. Relevant fetched branch families include worker/fs147-policy-adapter, worker/fs147-readonly-claim-strict, worker/fs147-readonly-pipeline, worker/fs147-readonly-pipeline-actor-binding, fix/fs-001a-worker-execution-guard-review and historical p0-worker retry/restart/fencing branches. Enumeration is not a complete code audit of every branch.

STOP: orchestration contract requires Integration arbitration on overlapping active ownership. Do not patch PR #446's Worker entrypoint or copy the existing FS147 implementation into a duplicate. Integration must confirm #446 ownership, approve the integration base and assign the root `worker/**` pipeline path before an incremental application change. User explicitly launched this execution; the issue's older PREPARATION ONLY text is not treated as cancellation of that instruction.

