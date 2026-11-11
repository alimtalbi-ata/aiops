# P0 — Fail-closed tenant-scoped Run inventory in the single portal

Date: 2026-10-28. Source baseline: main `1ed749129e32ea9a8854c437c7de9a6a8b43e35b`.

## Problem and boundary

The portal reads `/api/runs` from Core for both `/api/portal/bootstrap`
and the home-page Run table. The current portal has no independently verified
actor-to-tenant ACL at this read boundary. Displaying tenant-scoped rows merely
because Core returned HTTP 200 risks leaking Run metadata across tenants.

## Narrow safety increment

`portal_read_models._valid("runs", ...)` rejects the **entire Run inventory**
if a root or nested row contains an explicit tenant, organization, workspace,
account or customer scope claim, including camelCase, snake_case and kebab-case
spellings. Even a null scope claim is rejected: absence of a value is not an
authorization grant. Uninspectable, excessively nested or oversized JSON-shaped
structures fail closed. A rejected inventory is represented as `runs=null`
and `states.runs=UNKNOWN`, not an empty/healthy inventory. The existing portal
bootstrap and home page use this same read model.

The response explicitly exposes `tenant_acl_qualified=false`. This is a
**defense-in-depth rejection guard**, not a complete tenant RBAC implementation.
Unscoped records are still `READABLE_UNVERIFIED`; no claim of Core identity
verification, source runtime attestation, or LIVE readiness is made.

## Validation and limitations

The existing `.github/workflows/quality.yml` runs
`tests/test_portal_read_models.py`. Added negative cases for tenant scope
aliases, nested claims, null values, root-level scope, deep structures and
bootstrap/home-page non-disclosure, plus the prior unscoped regression cases.
These are offline contract tests, not a real multi-tenant Core integration.

**Blocked / NOT_TESTED:** independent tenant identity, Core-side row-level
authorization, real Checkmk/Thruk observations, Grafana metrics, observed RAG,
NVIDIA NGX inference and Debian runtime. Before enabling tenant data, implement
authenticated actor/tenant context and enforce ACL in Core and at the portal
read boundary; test two real tenant principals against an isolated Core service.

No production access, no deploy, no LIVE action, no merge in this increment.
