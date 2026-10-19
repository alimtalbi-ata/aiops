# AIOps 2.0 — Project Continuity Record

**Author:** Abdelhalim Talbi  
**Repository:** https://github.com/alimtalbi-ata/aiops  
**Default branch:** `main` (protected by workflow; work on branches and propose PRs)  
**Last updated:** 2026-10-19

## Why this document exists

This is the restart point for future ChatGPT sessions and contributors. Read it before proposing work. Update it whenever a material decision, architecture, interface contract, operational discovery, test result, or delivery changes. Do not rely on chat history as the only record.

## Current direction

Consolidate AIOps 2.0 around one coherent runtime and operations experience. Reuse proven historical AIOps v1 / V145 capabilities when they are faster and safer to adapt than to rebuild. Do not equate a directory, old demo, PID file, or running process with a qualified component: inspect source, contracts, dependencies, tests, and runtime behavior first.

## Known environment snapshot (reported 2026-10-19)

- Host: `SRV-DEB-05`, Debian 13; working root `/home/aiops`.
- AIOps 2.0 runtime families exist, including V8 clean deployment line, V28.3.x Command Center line, and later architecture/implementation investigations.
- Reported active services include portal, core, worker, policy, RAG, intelligence, Temporal, twin, copilot, simulator, evidence, integration, Prometheus and Grafana. Re-check live state before every deployment; this is a dated snapshot, not a current guarantee.
- Historical AIOps v1 source and evidence live under `/home/aiops/aiops-v1`.
- V145-related directories include decision intelligence, evidence fusion/matrix/acquisition/enrichment, semantic evidence engine, decision adapter, functional bridge, functional read model and decision cockpit.
- A first read-only audit was attempted on 2026-10-19. Its terminal paste/output is partially corrupted; module presence and file listings are useful leads, but the report does not qualify these modules or prove their behavior.

## Non-negotiable operating rules

1. **Protect production.** No restart, destructive cleanup, migration, config change, token rotation or production cutover without explicit scope, backup/rollback and a verified preflight.
2. **Preserve main.** Work in a dedicated branch, commit to GitHub, and open a PR. Do not claim a commit exists until GitHub confirms it.
3. **Keep evidence.** Every change must include tests run, exact outcomes, limitations, changed files, and rollback notes. Distinguish source inspection, static tests, integration tests, and live production verification.
4. **No false qualification.** Never label a demo, synthetic run, expected output, or unexecuted test as a real runtime proof.
5. **Fail closed.** Missing, stale, contradictory or unproven evidence is `UNKNOWN`; it must not be silently treated as healthy or successful.
6. **Security boundary.** Keep secrets out of Git, reports, screenshots, chat and logs. Never commit `.env`, tokens, private keys, database files or production exports.
7. **Cumulative handover.** Keep architecture, decisions, component catalog, compatibility/contracts, test evidence and release notes in the repository and update them with every significant delivery.
8. **Reuse before rebuild.** Compare historical v1/V145 code and contracts with current runtime responsibilities; adapt only where boundaries and tests can be made explicit.
9. **Do not silently fallback.** If a preferred adapter/tool is unavailable, report it and require a documented fallback decision.
10. **Do not break PC11K5 fencing guarantees.** Ownership, fencing, preconditions, effect, evidence and reconciliation invariants must remain intact.

## Required reading order for a new session

1. `README.md`
2. `docs/PROJECT-CONTINUITY.md`
3. `docs/ARCHITECTURE-AND-BOUNDARIES.md`
4. `docs/DECISION-LOG.md`
5. `docs/COMPONENT-CATALOG-AND-REUSE.md`
6. `docs/QUALIFICATION-AND-CHANGE-PROTOCOL.md`
7. Latest release notes and evidence manifests for the target version.

## Latest source review (2026-10-19)

A focused GitHub source audit is recorded in [SOURCE-AUDIT-2026-10-19.md](SOURCE-AUDIT-2026-10-19.md). The safety patch was merged via [PR #5](https://github.com/alimtalbi-ata/aiops/pull/5) at commit `493336fb51fcda41d1ece8fc1822bb13f1ef232c`: P1 escalates before evidence checks; policy no longer defaults critic validation to true and requires explicit freshness/precondition/fencing/approval inputs; the worker blocks LIVE runs before generating placeholder evidence and marks the Run BLOCKED. Added `tests/test_policy_safety.py` and `.github/workflows/quality.yml`; GitHub Actions run [39223403723](https://github.com/alimtalbi-ata/aiops/actions/runs/39223403723) passed compileall, policy unit tests and static audit. Container build, runtime qualification and synthetic E2E remain unrun. The current main branch includes this conservative guard; LIVE execution is still not qualified. Container build, runtime qualification and synthetic E2E remain unrun. A second hardening change merged via [PR #7](https://github.com/alimtalbi-ata/aiops/pull/7), commit `1bdd7235687f8b2c7081278e4dd86b8a17939ff3`: fresh installs generate random secrets, existing `.env` files are preserved, preflight rejects default secrets outside explicit demo mode, and the admin/internal tokens are checked for consistency. A third change merged via [PR #9](https://github.com/alimtalbi-ata/aiops/pull/9), commit `e6251c1ce195937b1af6019e389c9f6b3f68e2dc`: runtime credential fallbacks were removed, Compose now requires explicit secrets, the secure template is blank, and known demo values are isolated in `config/.env.demo.example`. CI run [39224781141](https://github.com/alimtalbi-ata/aiops/actions/runs/39224781141) passed Python compilation, policy tests, secret-preflight tests, static checks and `docker compose config`.

## Next work queue

- [x] Add deterministic policy safety tests and run them in GitHub Actions; preserve the run link in the source audit.
- [ ] Review and merge the LIVE safety patch only after tests pass and its diff is inspected.
- [ ] Run a corrected, truly read-only inventory of historical v1/V145 source, contracts, tests, and service ownership.
- [x] Audit and harden runtime secret fallbacks and Compose interpolation; merged via PR #9 with passing CI.
- [ ] Inspect current repository tree and deployment files; compare Git-tracked code to the host deployment without copying secrets.
- [ ] Build a reuse matrix: reuse unchanged / adapt behind adapter / replace / retire, each with evidence and owner.
- [ ] Establish one canonical incident/run/evidence/decision schema and versioned API contracts.
- [ ] Verify the complete event path from ingestion to correlation, CMDB enrichment, evidence acquisition, analysis/critic, policy gate, HITL, remediation, verification, rollback and learning.
- [ ] Test replay/simulation separately from LIVE execution, with explicit authorization and idempotency.
- [ ] Add deterministic E2E and failure-injection qualification before enabling any new live action.
- [ ] Produce cumulative deployment ZIP and updated docs/evidence for each version where a release is requested.

## Update rule

Every material change must update this record and the relevant architecture/decision/component/test documents in the same branch/PR. Add a dated entry to `docs/DECISION-LOG.md`; include commit/PR links after they exist. At session end, record exact next steps and unresolved risks here.


## AIOps 2.0 development continuation — Portal operator boundary

**Date:** 2026-10-19  
**Branch:** `feat/portal-operator-auth-v2`  
**Status:** Implementation committed to a dedicated branch; PR #16 open as draft. GitHub Actions quality run #105 passed.

### Change scope
- Portal startup now fails closed if `AIOPS_PORTAL_OPERATOR_TOKEN` is absent.
- `POST /api/demo` and `POST /api/copilot` require a Bearer token validated with constant-time comparison.
- Copilot input is validated and bounded to 1–4,000 characters.
- Upstream exceptions from these mutation/AI routes return a generic 503 without leaking internal exception text, URLs or secrets.
- Portal UI asks for the operator token at runtime, sends it in the Authorization header, and does not persist it in browser storage.
- Fresh-install secret generation creates a separate random portal operator token. Compose requires it explicitly. The secure env template, preflight, static audit and CI test job were updated.

### Qualification
New unit tests cover valid/missing/incorrect auth, wrong scheme, empty token, Copilot question bounds, upstream error redaction and success passthrough. GitHub Actions run [39274829807](https://github.com/alimtalbi-ata/aiops/actions/runs/39274829807) passed Python compileall, policy tests, portal authorization tests (8 cases), secret-preflight tests, static audit, and Compose config validation with generated secrets. This is CI qualification only; it does not replace browser/API integration or production qualification.

### Limits and next gates
- Read-only dashboard/bootstrap routes are not yet protected by operator authentication; determine the intended public-read policy before external exposure.
- The portal token is a shared operator secret, not an identity provider, per-user RBAC, or MFA. Deploy behind TLS and a trusted access boundary; plan identity-provider integration for production.
- Verify that all reverse proxies redact Authorization headers and never log credentials.
- Test rate limits, CSRF/origin policy, content-security policy, browser UX, Core timeout/idempotency and compose/preflight behavior.
- Keep DEMO synthetic. LIVE execution remains blocked by the existing canonical worker/policy safety controls.
- No runtime deployment, restart, database change, or PC11K5 fencing modification was performed.


### Latest CI evidence — 2026-10-19
- [PR #16](https://github.com/alimtalbi-ata/aiops/pull/16) is open as draft, branch `feat/portal-operator-auth-v2`, targeting `main`.
- Quality workflow run [39274829807](https://github.com/alimtalbi-ata/aiops/actions/runs/39274829807) completed successfully.
- Portal auth unit tests: 8/8 passed.
- Policy tests: 7/7 passed.
- Secret preflight, static repository audit and Compose configuration validation: PASS.
- No runtime deployment or live service test was performed. Keep the PR in draft until broader security/UI acceptance gates are addressed.


## Portal security follow-up — authenticated read model and browser boundary (2026-10-19)

- Portal `GET /api/portal/bootstrap` now requires the operator Bearer token; upstream read failures are normalized by the same safe error wrapper.
- `GET /` now serves a login shell only. Operational dashboard/run/twin data is fetched client-side after successful operator authentication, rather than embedded in unauthenticated HTML.
- Added response headers: CSP, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and a restrictive `Permissions-Policy`.
- Privileged POST routes reject a supplied cross-origin `Origin` that does not match the request origin/host. Requests without an Origin header are still allowed for non-browser clients, with Bearer auth required.
- UI uses textContent for returned JSON/data and does not persist the operator token to local/session storage.
- Tests expanded to cover authenticated read boundary, unauthenticated POSTs, login-shell response headers and origin validation. The CI run for these latest commits is pending.
- CSP currently permits inline script/style because the current UI is a single embedded page. A next hardening iteration should move scripts/styles into versioned static assets or use nonces/hashes before production exposure.
- No runtime deployment was performed. Reverse-proxy TLS/trusted-forwarded-header configuration, rate limiting, live browser testing and production qualification remain open.


### Latest portal security qualification — 2026-10-19
- GitHub Actions run [39275563557](https://github.com/alimtalbi-ata/aiops/actions/runs/39275563557) passed after the authenticated-read and browser-boundary changes.
- Portal boundary tests: 14/14 passed.
- Policy tests: 7/7 passed.
- Secret preflight, static audit, Python compileall and Compose config validation: PASS.
- PR #16 remains draft pending actual browser/proxy integration, rate limiting, TLS/trusted-proxy review and production qualification.


## Shared HTTP retry safety — 2026-10-19

- Audited `app/shared/http.py`: the previous helper retried POST requests after timeouts/errors. For side-effecting operations, the server may have committed an incident/run while the response was lost, so an automatic retry can duplicate work.
- Changed default retry policy: GET retries up to two times; POST makes one attempt by default. A caller may request an explicit retry override only when the operation's idempotency contract is understood.
- Added unit coverage for GET retries, POST no-retry, explicit override, and internal authentication headers; added the test to CI.
- This deliberately favors safety over automatic recovery for ambiguous POST outcomes. A timed-out POST must be reconciled against the canonical run/incident state before an operator repeats it.
- CI result for this latest change is pending.


### Latest quality run after HTTP retry hardening — 2026-10-19
- GitHub Actions run [39276121809](https://github.com/alimtalbi-ata/aiops/actions/runs/39276121809) completed successfully after the shared HTTP retry changes.
- Portal boundary tests: 14/14 passed; shared HTTP retry-safety tests: 4/4 passed; existing policy tests: 7/7 passed.
- Secret preflight, static repository audit, Python compilation and Compose validation: PASS.
- Default HTTP policy is now GET retry (up to two retries) and POST single attempt. The public helper functions allow an explicit retry override only when a caller can justify the idempotency contract.
- An ambiguous POST timeout must be reconciled against canonical state before repeating an operation; do not blindly resubmit.
- PR #16 remains draft. CI passing is not a substitute for browser/proxy integration or production qualification.


## Install/qualification loop — authenticated E2E correction (2026-10-19)

- During the next development loop, reviewed the existing install/qualification path after adding operator authentication.
- Found that `tests/synthetic-e2e.sh` still called the bootstrap and demo endpoints without a Bearer token. It would fail against the new Portal security boundary and did not assert that unauthenticated access was rejected.
- Updated the synthetic E2E script to read the dedicated operator token from the existing local `.env`, assert that bootstrap and demo are rejected without authentication, then execute the synthetic flow with authentication and wait for the generated run to appear.
- Added CI shell syntax checks for install, preflight, qualification and E2E scripts, and static assertions that the E2E security checks are present.
- No server-side SCP/SSH deployment was possible from this session: available connected GitHub actions support repository changes and CI, not arbitrary shell access to `SRV-DEB-05`. No runtime installation, container restart or live E2E is claimed.
- Next loop gate: CI must pass, then the operator runs the guarded install/qualification sequence on the intended isolated target with backup and rollback ready. Do not apply this draft PR directly to production.


## Canonical command idempotency scope — 2026-10-19

- Source review found that Core looked up command receipts by globally unique `idempotency_key` and replayed the stored response without checking that the receipt belonged to the requested run and command.
- Added a pure helper that replays a receipt only when both `run_id` and `command` match; cross-run or cross-command key reuse now returns HTTP 409 rather than an unrelated success response.
- Added five deterministic unit tests for absent receipts, exact replay, cross-run conflict, cross-command conflict and response preservation; wired them into CI.
- The schema still intentionally treats the idempotency key as globally unique. This change makes that global contract explicit and fail-closed; changing it to per-run uniqueness would require a separate migration and compatibility decision.
- Latest CI must pass before this source change is considered qualified. No DB migration, deployment or runtime mutation was performed.
