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


## ADR-0013 — Protect privileged Portal actions with an explicit operator token

- **Date:** 2026-10-19
- **Status:** Proposed in `feat/portal-operator-auth-v2`; awaiting CI and review.
- **Decision:** Require a separately generated `AIOPS_PORTAL_OPERATOR_TOKEN` for Portal DEMO launch and Copilot calls. Reject missing/invalid Bearer credentials; use constant-time comparison; do not persist the token in browser storage. Keep internal service credentials server-side.
- **Reason:** The historical and current Portal route review found privileged POST handlers without an explicit operator authorization boundary. A missing admin token must not disable authorization.
- **Consequences:** Fresh installs generate a unique token; Compose/preflight require it. Operators must enter the token into the Portal UI for privileged interactions. Existing `.env` files are not automatically rewritten or rotated; operators upgrading must deliberately add a strong independent token before deploying this branch.
- **Limitations:** This shared token is not per-user identity, RBAC, MFA or an identity-provider integration. Read-only routes remain a separate policy decision. Production exposure still requires TLS, a trusted proxy/access boundary, rate limiting and credential-safe logging.
- **Safety:** DEMO remains synthetic. This does not enable LIVE remediation or modify the canonical policy gate, worker guard or PC11K5 fencing invariant.
- **Qualification:** New unit tests and CI steps are committed, but results are pending. No runtime deployment or production qualification is claimed.

## ADR-0019 — Grounded Copilot read-only safety slice (2026-10-27)

- **Status:** Proposed on stacked draft PR; not deployed or qualified. Number reserved after ADR-0013 through ADR-0018 proposed in draft PR #39; reconcile final numbering when integrating the PRs.
- **Decision:** Replace question-independent Copilot summaries and arbitrary confidence with deterministic supported intents, exact source citations and abstention. Require internal gateway authentication and an operator-authenticated Portal (draft PR #16); deny LIVE run evidence until user-level ACL qualification. Stage vendor/internal documents only with rights, product/version, tenant ACL and provenance, using lexical retrieval as a testable foundation rather than claiming a complete RAG.
- **Rationale:** Avoid public leakage, unsupported claims, cross-run evidence contamination and misleading confidence. Internal token is not user RBAC.
- **Open:** Integrate PR #39 ADRs, persistent hybrid index, identity/tenant claims and actual runtime tests before promotion.
