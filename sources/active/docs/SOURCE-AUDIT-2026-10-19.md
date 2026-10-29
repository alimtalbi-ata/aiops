# Source audit and safety remediation — 2026-10-19

**Author:** Abdelhalim Talbi  
**Target:** GitHub `main` at `8f9e6e7356777a0331b36a14c2fc325001cae41e`  
**Work branch:** `fix/live-safety-gates-2026-10-19` — merged by [PR #5](https://github.com/alimtalbi-ata/aiops/pull/5) as commit `493336fb51fcda41d1ece8fc1822bb13f1ef232c`; deployment-secret hardening merged by [PR #7](https://github.com/alimtalbi-ata/aiops/pull/7) as commit `1bdd7235687f8b2c7081278e4dd86b8a17939ff3`  
**Scope:** Read-only source review followed by a narrow fail-closed safety patch. No production host or running service was accessed or modified.

## Evidence boundary

This review is based on source files retrieved from GitHub. It is not a runtime test, penetration test, or production qualification. Existing shell qualification scripts were inspected but not executed in a live stack. The host inventory mentioned in the continuity record is separate and was not independently re-run in this change.

## Findings

### F-01 — LIVE stages generated generic evidence and hard-coded confidence

**Severity:** Critical safety gap  
**Evidence:** `app/worker/main.py` previously set `synthetic = mode != 'LIVE'`, then created evidence for every stage with a generic claim such as “stage completed”, and assigned confidence `0.94` (or `0.91` for analyst/critic stages). No real DGX/NIM, RAG, CMDB, observation or remediation adapter is invoked in this code path.

**Risk:** A LIVE run could record synthetic-shaped placeholder output as non-synthetic evidence and advance the workflow without actual source-backed analysis.

**Change on this branch:** LIVE stage execution now records `LIVE_ADAPTER_UNAVAILABLE`, creates no evidence, returns BLOCKED and transitions the Run to BLOCKED. This remains a conservative guard until qualified LIVE adapters exist.

### F-02 — Policy defaulted critic validation to true and used incomplete preconditions

**Severity:** Critical safety gap  
**Evidence:** `app/policy/main.py` previously defined `critic_validated: bool = True`; the worker explicitly sent `critic_validated: True`, confidence `.94`, severity `P1` and command `EXECUTE`. The old policy did not block P1 and could return ALLOW for this command when evidence_count was nonzero.

**Risk:** An optimistic caller default and hard-coded worker values could satisfy the policy gate without independently verified critic evidence, evidence freshness, preconditions, fencing/ownership or human approval.

**Change on this branch:** critic validation is now required input; modes, commands and severity are constrained; P1 always escalates; LIVE effects require verified fresh evidence, preconditions, fencing/ownership, approval where applicable, redundancy and confidence. The current worker's LIVE guard blocks before the placeholder evidence path, so no LIVE adapter is implicitly treated as qualified.

### F-03 — A blocked stage did not necessarily block the Run record

**Severity:** High  
**Evidence:** `app/core/main.py` event ingestion updates stage state and Run version, but does not set the Run lifecycle status to BLOCKED when an event has status BLOCKED. The workflow returned a BLOCKED result without a matching lifecycle command in the previous code.

**Change on this branch:** the LIVE adapter guard issues an idempotent Core `BLOCK` command after recording the blocking event, so stage/event state and Run lifecycle status agree for this guard path. General policy-gate lifecycle reconciliation remains a follow-up.

### F-04 — Development credentials are committed as defaults

**Severity:** High; deployment hardening follow-up  
**Evidence:** `config/.env.example`, `compose.yml`, `app/core/main.py`, `app/worker/main.py` and `app/shared/http.py` contain a known development fallback credential. `docs/SECURITY.md` already labels it demo-only.

**Risk:** A deployment that fails to replace demo values can run with guessable credentials. A documentation warning does not enforce secure configuration.

**Disposition:** Preflight enforcement and secure generation for fresh installs are now implemented in PR #7. Existing `.env` files containing defaults fail preflight unless explicit demo mode is set. Application-level fallback literals were removed by PR #9; missing credentials now fail fast and Compose requires explicit values. The shared token is injected into Portal and Copilot as well as Core, worker and simulator. CI validates Compose interpolation with generated secrets. Full container build and E2E are still required.

### F-05 — Qualification scripts prove structure/reachability, not safety semantics

**Evidence:** `tests/static-audit.sh` performs Python syntax parsing and grep checks; `tests/qualification.sh` checks container existence and selected HTTP endpoints; `tests/synthetic-e2e.sh` starts a demo and waits for a run to appear in the portal inventory.

**Risk:** These tests do not establish that P1 is escalated, a missing critic blocks execution, synthetic evidence cannot be passed off as real, fencing is verified, or rollback/reconciliation works after partial effects.

**Disposition:** Add deterministic policy unit tests and then extend E2E/failure-injection coverage. This branch adds `tests/test_policy_safety.py`. GitHub Actions run 39223403723 passed Python compilation, all policy unit tests and `tests/static-audit.sh` on commit `021dbea440079d5ceb5cc73bc1aeb75690031b73`.

## Patch summary

- Policy now requires explicit critic validation and explicit LIVE evidence/precondition/fencing state.
- P1 is always escalated.
- LIVE worker path blocks before generating generic evidence because the repository does not yet contain qualified LIVE adapters.
- The guard transitions the canonical Run to BLOCKED.
- Added deterministic unit cases for P1, no evidence, missing fencing, missing approval, fully qualified P2, and DEMO-only simulation.

## Qualification status

- GitHub source inspection: **PASS**
- Python compileall: **PASS** in GitHub Actions run [39223403723](https://github.com/alimtalbi-ata/aiops/actions/runs/39223403723)
- Policy safety unit tests: **PASS** in GitHub Actions run [39223403723](https://github.com/alimtalbi-ata/aiops/actions/runs/39223403723)
- Static repository audit: **PASS** in GitHub Actions run [39223403723](https://github.com/alimtalbi-ata/aiops/actions/runs/39223403723)
- Container build / runtime qualification: **NOT RUN**
- Synthetic E2E: **NOT RUN**
- Live/production verification: **NOT RUN**
- Deployment safety: no deployment or production action performed

## Required next work

1. Add an explicit `policy-safety` test to the standard qualification entry point and retain the GitHub Actions gate.
3. Fix the general BLOCKED event/Run lifecycle reconciliation path.
4. Remove insecure secret fallbacks and make deployment preflight fail on default secrets outside explicit demo mode.
5. Implement real evidence adapters with provenance, timestamps, freshness and source identity before allowing LIVE workflow progression.
6. Implement true analyst/critic outputs, CMDB/RAG connectors, HITL approval evidence, remediation adapters, post-action verification, rollback and reconciliation; keep all LIVE actions blocked until each capability is qualified.
7. Add Temporal retry/replay tests for idempotency under a crash between event append and activity completion.
