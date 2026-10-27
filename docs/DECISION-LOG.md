# AIOps 2.0 — Decision Log

**Author:** Abdelhalim Talbi  
Use this file for durable architecture/product decisions. Add new entries; do not silently rewrite history. Status may be changed with a dated rationale.

## ADR-0001 — Keep one canonical runtime

- **Date:** 2026-10-19
- **Status:** Accepted
- **Decision:** Consolidate around the AIOps 2.0 runtime and its canonical Run/Incident state; do not build another parallel orchestration/control plane.
- **Reason:** Reduce duplicate state, integration drift and operational burden.
- **Consequences:** Historical platforms are reused through adapters and explicit contracts; production cutover requires qualification and rollback.

## ADR-0002 — Reuse AIOps v1/V145 before rebuilding

- **Date:** 2026-10-19
- **Status:** Accepted
- **Decision:** When a historical capability is faster to reuse and can meet current safety/quality standards, adapt it rather than rewrite it.
- **Candidates:** Decision intelligence; evidence fusion/matrix/acquisition/enrichment; semantic evidence engine; decision adapter; functional bridge/read model; decision cockpit.
- **Qualification condition:** Inspect source, dependencies, contract, tests, ownership, data stores and actual behavior. Directory presence or old demo status is insufficient.
- **Consequences:** Maintain a reuse matrix and record why each component is reused, adapted, replaced or retired.

## ADR-0003 — Keep the Portal out of direct database writes

- **Date:** Existing repository README; reaffirmed 2026-10-19
- **Status:** Accepted; implementation must be tested
- **Decision:** Portal calls Core APIs; Core owns state transitions and persistence boundaries.
- **Reason:** Consistent authorization, validation, audit and schema evolution.

## ADR-0004 — Durable orchestration owns Run progression

- **Date:** Existing repository README; reaffirmed 2026-10-19
- **Status:** Accepted; implementation must be tested
- **Decision:** Temporal/Worker own durable workflow progression; n8n is an integration boundary and must not own Run state.
- **Reason:** Retry, recovery and lifecycle consistency.

## ADR-0005 — Evidence and events are auditable records

- **Date:** Existing repository README; reaffirmed 2026-10-19
- **Status:** Accepted; implementation must be tested
- **Decision:** Events and Evidence are append-only; provenance/freshness and decision links are required. Unknown or missing proof stays `UNKNOWN`.
- **Reason:** Reproducibility, forensic traceability and safe decisions.

## ADR-0006 — Fail-closed live remediation

- **Date:** Existing repository README and prior project constraints; reaffirmed 2026-10-19
- **Status:** Accepted
- **Decision:** Live actions require deterministic policy authorization, explicit mode, validated identity/ownership/fencing, preconditions, approval when required, idempotency, verification and reconciliation. LLM confidence alone never authorizes a high-risk action.
- **Reason:** Prevent duplicate ownership, stale decisions, unsafe actions and unverified recovery.

## ADR-0007 — Preserve the PC11K5 fencing invariant

- **Date:** 2026-10-19
- **Status:** Accepted
- **Decision:** Preserve the invariant chain: claim → fencing/ownership → preconditions → effect → evidence → reconciliation. No integration may weaken stale-owner/duplicate-owner blocking.
- **Reason:** Correctness under concurrency and partial failure.
- **Qualification:** Existing fencing/concurrency/PostgreSQL tests must be included in regression runs.

## ADR-0008 — GitHub is the durable handover source

- **Date:** 2026-10-19
- **Status:** Accepted
- **Decision:** Keep continuity, architecture, component descriptions, decisions, test protocols, release notes and next actions in `alimtalbi-ata/aiops`. Work on branches, commit, and open PRs; preserve `main`.
- **Rule:** Every significant development session must update the relevant docs before closing. Verify commit/PR URLs before reporting completion.

## ADR-0009 — Separate test evidence by strength

- **Date:** 2026-10-19
- **Status:** Accepted
- **Decision:** Label evidence as source inspection, static test, unit/contract test, isolated integration, synthetic E2E, or live production verification.
- **Reason:** Avoid claiming runtime or production qualification from static evidence.

## ADR-0010 — Block LIVE execution until real adapters are qualified

- **Date:** 2026-10-19
- **Status:** Accepted as an interim safety control; merged in PR #5 at commit `493336fb51fcda41d1ece8fc1822bb13f1ef232c`
- **Decision:** The current worker must not progress LIVE runs by emitting generic stage-completion evidence or fixed confidence values. It records an explicit adapter-unavailable event and transitions the Run to BLOCKED.
- **Reason:** The repository does not yet provide qualified live evidence acquisition, CMDB/RAG/analyst/critic integrations, HITL approval evidence, or verified remediation/rollback adapters. Synthetic placeholder claims must not be marked non-synthetic merely because mode is LIVE.
- **Policy changes:** P1 always escalates; critic validation is required input rather than a trusted default; LIVE actions require explicit evidence freshness, preconditions, fencing/ownership, and human approval for effects.
- **Consequence:** LIVE execution remains intentionally unavailable until each adapter and end-to-end failure/recovery path is implemented and qualified. DEMO/REPLAY/STORY remain explicitly synthetic.
- **Qualification:** Deterministic unit cases are added, but they must be executed in the pinned runtime before merge. This ADR does not claim production qualification.

## ADR-0011 — Generate secrets on fresh install and reject insecure defaults

- **Date:** 2026-10-19
- **Status:** Accepted; merged via [PR #7](https://github.com/alimtalbi-ata/aiops/pull/7) at commit `1bdd7235687f8b2c7081278e4dd86b8a17939ff3`.
- **Decision:** New installs generate random credentials and set restrictive `.env` permissions. Existing `.env` files are not silently overwritten or rotated. Preflight rejects known defaults unless the operator explicitly opts into isolated demo mode. Internal admin/token values must match under the current service contract.
- **Reason:** Prevent accidental deployment with public, predictable demo credentials without breaking existing database credentials through automatic rotation.
- **Qualification:** CI tests generation, permission mode, non-rotation, default rejection, demo opt-in and token consistency. Full deployment/upgrade qualification remains required.

## ADR-0012 — No insecure application or Compose credential fallback

- **Date:** 2026-10-19
- **Status:** Accepted; merged via [PR #9](https://github.com/alimtalbi-ata/aiops/pull/9) at commit `e6251c1ce195937b1af6019e389c9f6b3f68e2dc`.
- **Decision:** Application services fail fast when internal credentials are absent. Compose requires secret variables rather than silently substituting known demo values. The secure environment template has blank secret fields; the known-value demo template is separate and opts into demo mode explicitly.
- **Reason:** A standard or direct Compose deployment must not silently start with a public development credential.
- **Consequence:** All services using the shared HTTP client must receive the same internal token through configuration. The installer generates it once and assigns it consistently to the current admin/internal aliases.
- **Qualification:** CI passes Python compileall, policy and secret-preflight tests, static audit, and Compose configuration validation. Full container build and synthetic E2E remain outstanding.

## ADR-0013 — Explicit authenticated simulator → Core API network path

- **Date:** 2026-10-27
- **Status:** Proposed; awaiting PR review and isolated runtime qualification
- **Decision:** Attach `aiops2-core` to `aiops2-execution` in addition to its existing control/data networks, so the simulator can call its authenticated Core API without being connected directly to PostgreSQL, control, integration or public networks.
- **Reason:** On `main`, simulator and Core have no common Docker network, despite `CORE_URL` pointing to Core. This prevents the simulator's documented API proxy, scenario registration and launch paths from working through that hostname.
- **Risk and control:** Core becomes reachable from execution-network peers. Preserve token validation on mutating Core APIs and keep the simulator confined to execution. Validate the rendered Compose graph in CI and test real DNS/HTTP connectivity in an isolated stack before promotion.
- **Rollback:** Remove `aiops2-execution` from the Core service network list and revert the corresponding contract test and documentation. Do not restart a production stack as part of this change.
