# Portal operational-state integration — security contract (draft)

Status: **DESIGN ONLY / HOLD / NO_GO**. This document grants no permission to deploy or merge.

## Verified existing behavior

- `app/portal/main.py`: `GET /api/portal/bootstrap` aggregates Core and Twin via `shared.http.get_json`; it does not derive an authenticated human actor/tenant, validate scope, or provide an authoritative observation timestamp.
- `app/shared/http.py`: `get_json` uses a service-level internal bearer token and `X-AIOPS-Request: internal`. This is **service authentication**, not evidence of a browser user's tenant authorization.
- `app/portal/main.py`: `_get` converts upstream exceptions into `{status:'UNKNOWN',error_type:...}`; `/runs` and `/` render HTML server-side and do not call the new JS component.
- `app/portal/components/operational_state.mjs`: browser accepts only `scope_verified === true` and `authorization_source === 'server'` for READY/EMPTY; freshness requires `observed_at`.

## Preconditions for a new read-only projection

1. Identify an existing **trusted, server-verified identity source** for the requesting human actor and tenant, with documented authentication, tenant membership, and authorization policy. If none exists, **do not expose an operational projection**.
2. Authorize the actor to view the requested records *at the data source or trusted server boundary*, before serialization. Do not trust browser-provided tenant IDs, headers, query parameters, or `scope_verified` flags as authorization evidence.
3. Never equate the shared `AIOPS_INTERNAL_TOKEN` / service bearer with end-user authorization. Prevent cross-tenant results, including through caches and error messages.
4. Use an authoritative source observation timestamp (not the API response time). Missing/invalid/stale/future observation timestamps must fail closed to UNKNOWN.
5. Return a minimal envelope **only on successful authorization and scope verification**:

```json
{"records":[],"observed_at":"2026-11-10T16:24:00Z","scope_verified":true,"authorization_source":"server"}
```

The example is a schema illustration, **not real observation evidence**. An empty array means a *verified fresh empty result*, never an upstream failure. Deny anonymous and unauthorized access with 401/403, without tenant data or secret-bearing diagnostics. Do not generate `scope_verified:true` client-side or infer it from HTTP 200.

## Integration acceptance matrix (must be automated)

| Case | Expected outcome |
| --- | --- |
| Anonymous, expired session | 401, no records |
| Authenticated actor, wrong tenant | 403, no records |
| Service token without end-user identity | Denied / no projection |
| Unverified source scope | UNKNOWN, no result |
| Missing, invalid, stale or future `observed_at` | UNKNOWN |
| Fresh, scoped, nonempty data | READY |
| Fresh, scoped, empty data | EMPTY |
| Upstream failure | ERROR, sanitized diagnostic |
| Hung read | UNKNOWN timeout, abort signal |
| Rapid filter changes / late completion | Latest request only |
| Malicious HTML and secret-bearing error | Inert DOM text; no secret in rendered UI |
| Retry / assistive technology | Native keyboard button; correct live-region role |

## Required evidence before GO

- Unit tests for server-side actor/tenant authorization and source timestamp semantics.
- Integration test on the **actual portal route**, using mock authorized and unauthorized upstream responses, and Chromium acceptance of the rendered page.
- CI checks and Debian environment qualification, followed by explicit release authorization.

Keep PR #537, #539 and #540 in DRAFT. No merge, deployment, automation change, or Debian modification.

## Source audit: Core endpoints (verified on stacked branch)

- `app/core/main.py` `GET /api/runs`: `list_runs()` executes `select ... from aiops.runs order by created_at desc limit 100` without an actor/tenant filter in the handler and without an authorization dependency in its signature. This is a global run listing in the inspected implementation.
- `app/core/main.py` `GET /api/dashboard`: `dashboard()` aggregates counts from `aiops.runs`, `aiops.twin_nodes`, and `aiops.incidents` without actor/tenant predicates in the handler. These aggregates cannot be presented as tenant-qualified evidence.
- These observations describe the inspected handlers; they do not establish whether other infrastructure restricts reachability. Network restrictions or service-level bearer tokens do not, by themselves, establish end-user tenant scoping.
- **Do not expose these global responses as scoped user projections.** Identify and test an authoritative identity/tenant model and authorized data queries before introducing the proposed endpoint. If such a model is not available, retain UNKNOWN and HOLD.

## Identity-source audit (additional blocking finding)

- In the inspected `app/portal/main.py`, no authentication middleware, request-state identity, or per-route user/tenant dependency is defined. This does **not** exclude identity enforcement outside this file; an ingress or identity proxy would need separate proof and trusted-header handling tests.
- In `app/core/main.py`, the `auth(token)` helper checks a shared internal token. Several write routes call it; this establishes a service credential check, not an independently verified human identity or tenant membership.
- `record_proposal_approval` reads `actor_id` and `actor_role` from the request payload after the internal-token check. Those values must **not** be reused as authenticated browser identity for the portal projection. This is a finding about the source of the fields, not a claim that the approval workflow is exploitable.
- **Decision gate:** before implementing a user-scoped read endpoint, produce a verified trust-boundary diagram (browser -> ingress/IdP -> portal -> Core/DB), the source and verification of actor and tenant claims, cross-tenant negative tests, and a documented policy owner. Otherwise keep the projection unavailable.

## Deployment topology audit: Compose (configuration only)

- `compose.yml` publishes the portal container on `${AIOPS_BIND_IP:-127.0.0.1}:${AIOPS_PORTAL_HOST_PORT:-7777}:777`. The default bind is loopback, but `AIOPS_BIND_IP` can change it. This is a configuration default, **not evidence of actual Debian runtime settings**.
- The inspected `aiops2-portal` service joins `aiops2-public` and `aiops2-control` and carries `AIOPS_INTERNAL_TOKEN` to make internal calls. The inspected Compose file does not configure an OIDC identity provider, authenticated ingress, or reverse proxy for this service. External host-level controls may still exist and require independent qualification.
- **Debian qualification must collect, without changing it:** effective Compose config and environment (with secrets redacted), active bind address, firewall/proxy/SSO policy, TLS/session identity flow, trusted headers and actor/tenant claim validation, and cross-tenant access tests. Do not infer public accessibility or safety solely from the Compose default.

## Existing automated boundary coverage (scope limitation)

- `tests/test_internal_auth.py` checks that Evidence read/write and Policy check deny absent or invalid **internal service tokens**. It also checks a missing Evidence secret fails closed. These are useful controls, but they **do not** establish portal user authentication, verified actor/tenant claims, or cross-tenant filtering.
- `tests/test_portal_demo.py` checks synthetic demo launch behavior and idempotency, not tenant-scoped read authorization.
- A green existing CI run must not be interpreted as passing the new portal actor/tenant acceptance matrix until new integration and negative authorization tests exist.

## Implementation checkpoint: disconnected projection policy (PR #543)

- `app/portal/operational_projection.py` is a **pure, disconnected policy helper**. It is not a route, authentication middleware, identity verifier, or authorization provider. No browser-visible endpoint calls it.
- It denies absent/unverified actor assertions, missing tenant membership, tenant/source mismatch, missing source scope verification, invalid or out-of-window observation times, and invalid freshness budgets. Its positive-path envelope is only valid when **every input is constructed by a trusted server component**.
- `tests/test_portal_operational_projection.py` covers these policy cases with **synthetic identities and sources**. The test data are not proof that real actor identity, tenant membership, or a tenant-scoped DB query exist.
- The CI workflow also executes `tests/test_portal_auth_contract_guard.py` and `node --test app/portal/components/operational_state.test.mjs`. The latest verified four-workflow green run was commit `5c4c56b`, including quality gates #8520. This is **unit/CI qualification only**, not integrated Chromium acceptance or Debian evidence.

### Unresolved ownership and evidence required for HTTP integration

1. Identify the trusted authentication mechanism (IdP/ingress/session) and prove that the portal verifies actor identity independently of browser-supplied fields. A forwarded header alone is insufficient without an enforced trusted ingress boundary.
2. Identify the authoritative tenant membership service or schema and its owner; verify revocation and denial of cross-tenant requests.
3. Provide a tenant-scoped query that never reads the global Core `/api/runs` or `/api/dashboard` responses as a source of tenant-qualified data. Verify row-level filtering before serialization.
4. Decide how server-side scope evidence and source observation timestamps are established, including empty data and upstream failure semantics.
5. Only then connect a route, add anonymous/forged-header/cross-tenant/expired-session tests, and execute Chromium on the **actual integrated portal**. Debian qualification remains separate.

**Until those five items have owners and executable evidence, the policy helper must remain disconnected and the release decision remains HOLD / NO_GO.**

## Artifact-level qualification review: workflow #8533 / head 25b5586

The downloaded GitHub Actions artifacts were inspected, not just their workflow status:

- `aiops2-runtime-e2e-report`: synthetic Temporal run `RUN-6EFA56C514488C89`, `RESOLVED`, 13 evidence records, 0 effect receipts, `mode=DEMO`, `live_execution=disabled`; provider and twin evidence are synthetic. This validates orchestration contracts only, not real model or production execution.
- `ai-core-evaluation.json`: 5/5 deterministic fixture cases, `provider=openai-compatible`, `model=ci-deterministic`, `execution_allowed=false`; all listed contract metrics score 1.0. The report explicitly says fixture data only and does not qualify real-model accuracy. `ledger_persistence.status=PASS` but `ledger_persistence.idempotent=false` — persistence success must not be conflated with idempotency.
- `aiops2-postgres-dr-report`: disposable PostgreSQL logical restore PASS; 31 tables, row hashes MATCH, corruption negative control PASS, target ephemeral CI DB, live system untouched. The artifact explicitly reports `temporal_mariadb_volumes=NOT_QUALIFIED`.
- `aiops2-mariadb-dr-report`: disposable MariaDB logical restore PASS; 2/2 rows, row integrity MATCH, corruption negative control PASS, no network, live system untouched.

### Follow-up acceptance work

1. Make evaluation-ledger writes idempotent on a stable evaluation identity (unique constraint/upsert or transaction-safe deduplication); add a replay test that submits the same evaluation twice and proves exactly one logical ledger record, unchanged payload/hash, and deterministic response. Do not change the reported gate to PASS until this replay test runs against the real persistence backend.
2. Add a separate Temporal MariaDB volume backup/restore rehearsal with disposable named volumes, explicit snapshot/restore evidence, integrity hashes and corruption negative control. Until then, retain `NOT_QUALIFIED`.
3. Keep real provider/model qualification separate from deterministic fixtures, and keep live execution disabled absent a separately approved test environment.

The CI workflow #8533 is green, but these artifact caveats remain release blockers where applicable. No production inference, no live effects, no Temporal MariaDB volume qualification, and no idempotent evaluation ledger are claimed.

## Correction: evaluation-ledger idempotency interpretation

A subsequent source review of `app/core/main.py` and `tests/test_model_evaluation_api.py` refines the earlier artifact interpretation:

- The first successful insert intentionally returns `idempotent=false` because it created a new evaluation row. That value alone is **not evidence of an idempotency defect**.
- The endpoint uses `ON CONFLICT(evaluation_id) DO NOTHING`, reads the prior row, returns `idempotent=true` when all persisted fields match, and returns HTTP 409 when the same ID is reused with different content.
- Existing unit tests cover first insert, duplicate same-content replay, conflicting-content rejection, and auth rejection. However, the tests use a mocked cursor/connection; they do **not** prove the unique constraint and transaction behavior against a live PostgreSQL instance.
- Therefore the accurate status is: **idempotency logic implemented; unit-tested with mocks; real-database concurrent/replay qualification not yet evidenced**. The artifact field `idempotent=false` records the initial insert path, not a failed replay test.

Next validation: run a PostgreSQL integration test against the migration-created schema; submit the same evaluation ID and payload twice (including concurrent requests), assert one row, first response `idempotent=false`, subsequent response(s) `idempotent=true`, stable persisted fields, and HTTP 409 for changed payload. Do not label this feature broken absent a failing integration test.

## Exact-SHA isolated PR qualification and route risk matrix (2026-11-11)

This section supersedes the historical PR #543 / workflow #8533 qualification statements **for isolated PR #627 only**. Head `4fbe9f68237f8bbd17db0f5e2f780e592dd1678e`: [quality run 43039219267](https://github.com/alimtalbi-ata/aiops/actions/runs/43039219267) completed **6/6 successful jobs**; the projection policy and authorization attestation guard steps both passed. V2.8 Core qualification (43039219280), Offline Integrity (43039219269), and Historical Trace (43039218887) also succeeded. This is CI qualification, **not** actor/tenant authorization qualification.

Source audit of `app/portal/main.py` and `app/shared/http.py` on the isolated branch:

| Portal route | Upstream data/action | Current human actor / tenant authorization evidence in handler | Gate before tenant-qualified access |
| --- | --- | --- | --- |
| `GET /api/portal/bootstrap` | Core dashboard/runs; Twin summary | No actor/tenant dependency; internal service bearer used upstream | P0.1 identity + P0.2 tenant-filtered Core/Twin queries; 401/403 and no-leak tests |
| `GET /`, `GET /runs`, `GET /policy` | Core dashboard/runs, Twin summary for home | No actor/tenant dependency; server-rendered pages | Authenticate page requests and authorize rows/counts before rendering |
| `GET /timeline` | Core runs/incidents, selected run detail, ledger and evidence | `run_id` validated for format and presence in a global run list, **not** tenant membership | Enforce resource ACL before detail/ledger/evidence fetch; cross-tenant 404/no-leak test |
| `GET /twin` | Twin summary, graph, fixed-node impact | No actor/tenant dependency in handler | Tenant-scope graph, nodes, edges, and impact before serialization |
| `POST /api/copilot` | Forwards browser JSON to Copilot | No human actor/tenant dependency in handler | Authorize actor, bound tenant and query scope; reject forged tenant hints |
| `POST /api/demo`, `POST /api/demo-enriched` | Synthetic incident/run creation | Feature flag and shared internal/admin bearer, not verified human identity | Keep disabled; any future role-based launch requires server-verified actor and audit |

**Trust boundary:** `shared.http._headers()` attaches `AIOPS_INTERNAL_TOKEN` (or admin fallback) to upstream requests. That token authenticates a service, **not** the browser actor. An upstream HTTP 200, membership in the global Core run registry, or a client-supplied tenant header cannot substitute for server-owned authorization. The route inventory is a source-code observation, not proof of runtime reachability or absence of an external ingress control.

**Acceptance sequence:** (1) document and test trusted IdP/session/ingress claim verification and revocation; (2) enforce actor→tenant/resource ACL before querying Core/Twin/Copilot; (3) prove anonymous 401, forged-header denial, wrong-tenant 403/404 with no data leak, and service-token-only denial; (4) qualify authorized fresh/empty/error cases at the actual HTTP route and browser; (5) collect separate Debian ingress evidence. Until then **HOLD / NO_GO** for integrated tenant reads and LIVE.
