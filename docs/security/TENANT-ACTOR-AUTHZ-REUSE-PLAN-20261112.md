# Tenant / actor authorization — cross-PR reuse review and integration plan

**Date:** 2026-11-12  
**Branch base:** `main@48deddadf365ac8a7cf71c7067f1c6cd740c32b6`  
**Status:** DESIGN / SOURCE REVIEW ONLY — no positive tenant read authorization is qualified.

## Executive decision

Do not create a parallel identity, tenant, or authorization subsystem. Reuse the existing focused work as a staged design:

1. **Runs read-scope groundwork:** PR #631 (current main-based candidate) supplies additive actor↔tenant grants, explicit Run↔tenant bindings, a bounded parameterized SQL read helper, and disposable PostgreSQL isolation/revocation tests. It does not authenticate the actor, expose an endpoint, implement RBAC roles, or qualify tenant reads.
2. **Actor delegation preflight:** PR #246 contains a Core-owned, server-side OAuth2 introspection design with pinned HTTPS, client authentication, issuer/audience, revocation, exact resource and short TTL checks. It deliberately has no ALLOW path because native GLPI actor rights and durable nonce/replay are not qualified. It is stacked on an old integration branch and must be selectively ported/rebased, not merged wholesale.
3. **Signed GLPI association and replay primitives:** PR #520 (based on current main) supplies reusable HMAC xref verification, a PostgreSQL nonce barrier, read-only Core/GLPI adapters, and an explicit actor/tenant authority contract. Its contract says there is no production identity provider. A passing source CI run is not real IdP/GLPI authority or end-to-end proof.
4. **GAMMA remains a consumer only:** do not enable its canonical reads until the canonical services independently enforce the same authenticated actor/tenant scope for Core, Evidence and Twin.

## Evidence inspected

### Current main and PR #631

- Current main at review time: `48deddadf365ac8a7cf71c7067f1c6cd740c32b6`.
- PR #631: `integration/tenant-actor-read-boundary-guard-20261111`, HEAD `2bd8cf4615f9fc185e74d43e91a0af5274f5a37e`, base SHA `0e232c9fdf4a519de36ba8035b506621854e0277`; compare reports 24 commits ahead / 2 behind. Its actual file delta is ten focused paths.
- Exact-head GitHub runs: tenant boundary run `43049964505` SUCCESS (both source-contract and real disposable PostgreSQL 16 isolation jobs succeeded); quality run `43049964742` SUCCESS. This is CI on the PR HEAD, not deployed service or real IdP qualification.
- `app/core/portal_tenant_runs.py` is a bounded (1–100) parameterized query joining `portal_run_tenant_bindings` and active `portal_actor_tenant_grants`. It validates actor-id shape but explicitly relies on the caller to supply an already verified actor. It has no HTTP route.
- `db/migrations/009_portal_tenant_actor_read_groundwork.sql` adds two additive mapping tables without backfill or implicit grants. It does not add a trusted identity provider, role/permission model, row-level security, or tenant keys to Incident/Evidence/Twin.
- Existing Portal bootstrap remains HTTP 503 `TENANT_ACL_NOT_QUALIFIED` after shared viewer authentication. The legacy Core dashboard and Run list are global and are not valid tenant authorization sources.

**Review disposition:** preserve #631 as the current fail-closed Runs foundation. Do not call it completed multi-tenant RBAC. Before merge, refresh it against current main and review the final exact-head diff/checks; no deployment follows from its CI.

### PR #246 — Core actor delegation preflight

- HEAD `a69e68523b6d690dcb8edbaf8bac57b2e8b8cca0`, based on `integration/enterprise-slice-main-20261031-2230` at `d5227f5c3981a53dd2a42d5384dce798cfaf0d33`; draft and not merged.
- `app/core/actor_resource_authz.py` performs per-request server-side HTTPS OAuth2 token introspection with client authentication, no ambient proxy, no redirects, bounded response, strict issuer/audience/subject/time/revocation and exact tenant/Run/Incident/GLPI resource claims.
- It explicitly returns UNKNOWN even after successful introspection and service-side xref because service GLPI readback is not proof of the human actor's native GLPI profile/entity rights. Durable nonce/replay and native actor authorization are still missing.
- The PR's architecture is useful, but its old base and route registration must be compared against current main before any selective port. Do not merge its branch history.

### PR #520 — GLPI actor/tenant authority and read-only chain

- HEAD `e41e570613e2243e353581c7ee93dce9525239ae`, based on current main SHA `0e232c9fdf4a519de36ba8035b506621854e0277`; draft, not merged.
- Reusable source candidates include `glpi_xref_hmac_verifier.py`, `glpi_xref_postgres_nonce.py`, `glpi_signed_xref_boundary.py`, and `glpi_server_readonly_assembly.py`.
- The verifier requires both a durable atomic nonce consumer and a server-owned actor ACL callback. The assembly requires separate server-owned Core and GLPI service credentials and independent read authorization.
- `docs/security/glpi-actor-tenant-authority-contract.md` explicitly says no production identity provider is currently implemented and defines the required server-derived principal, tenant membership, action/resource authorization, GLPI entity mapping and audit.
- Exact-head Quality workflow `42893375326` completed SUCCESS. Its tests use disposable mocks/CI PostgreSQL; no real IdP, production GLPI, Debian or live tenant qualification is claimed.

## Gaps that remain

1. **Trusted principal:** select and operate a real OIDC/identity provider or authenticated gateway; validate issuer, audience, signature/introspection, expiry, revocation, key rotation and stable subject. A shared Portal/Core service token is not an actor identity.
2. **Tenant membership and RBAC:** define a durable, audited membership/grant lifecycle (grantor, role, action, scope, effective time, revocation, issuer). PR #631 currently models membership only; it is not a role/permission model.
3. **Resource ownership:** define and enforce tenant scope for Incidents, Runs, Evidence, Twin nodes/edges/facts, observations, tickets, RAG documents and citations. Run-only side tables cannot protect other resource types.
4. **Every read path:** add server-side actor resolution and mandatory tenant filters to list, detail, aggregate/count, graph, impact, historical/as-of, evidence, dashboard, search and export queries. Do not rely on a UI filter or caller-supplied tenant parameter.
5. **Native GLPI authorization:** bind the OIDC subject to a GLPI user and independently check native profile/entity rights; a GLPI service account's ability to read a ticket is not the user's permission.
6. **Replay and audit:** install a durable nonce/replay barrier for signed associations, plus immutable authorization-decision audit records; ensure revocation takes effect on every read or has a rigorously bounded cache.
7. **Cross-tenant qualification:** positive A→A and B→B reads plus A→B denial for every resource family, including counts, graph edges, evidence links, citations and error paths; verify revoked memberships and concurrent changes using disposable PostgreSQL 16.
8. **GAMMA contract:** only after the above, expose versioned read-only Core/Evidence/Twin endpoints that independently enforce the caller's scope. GAMMA must not treat a tenant echo in upstream JSON as authorization.

## Implementation sequence

| Stage | Work | Exit evidence |
|---|---|---|
| A | Review/rebase #631; keep the fail-closed Portal and bounded Runs groundwork | Exact-head CI, reviewed migration and SQL; no route activation |
| B | Select the real IdP/gateway and define the signed principal/introspection contract; selectively port #246 only after compatibility review | Disposable IdP positive/negative HTTP tests, revocation, issuer/audience and resource binding |
| C | Integrate #520's signed xref/replay primitives only where Core/GLPI contracts match | Disposable PG16 replay/concurrency tests and independent GLPI actor-permission mock |
| D | Design canonical tenant ownership for Incident/Run/Evidence/Twin and add mandatory query scoping | Migration/rollback review and two-tenant tests for every query path |
| E | Wire read-only endpoints and Portal/GAMMA consumers | End-to-end A/B isolation, revocation, 401/403/503, no partial disclosure and exact-head CI |
| F | Consider deployment separately | Preservation/backup, exact image/source SHA, operator approval and tested rollback |

## Safety and release decision

- Keep `TENANT_ACL_NOT_QUALIFIED` and all existing LIVE/HITL fences unchanged.
- No default tenant, inferred tenant, historical backfill, browser identity header, or service-token-to-user impersonation.
- No global read fallback when a tenant-scoped query returns no rows.
- No merge, deployment, Docker operation, database migration on a live environment, GLPI write, or LIVE action is authorized by this review.
- The separate Docker storage recovery HOLD in issue #557 remains independent; do not touch the Debian host or its five stacks.

**Conclusion:** PR #631 is a useful, CI-backed Runs-only groundwork; PR #246 and #520 contain reusable security primitives and contracts. None of these individually or together currently supplies a qualified production actor/tenant authorization chain for all Core, Evidence and Twin data. Keep GAMMA canonical reads disabled until the full chain is independently demonstrated.
