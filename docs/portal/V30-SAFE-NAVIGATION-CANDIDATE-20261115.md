# V30 six-domain navigation candidate — 2026-11-15

**Scope:** isolated, presentation-only ESM navigation and CSS; not mounted in V30 runtime. No V1 change, service, DB, cron, deploy, API, token or LIVE write. The six anchors are placeholders for integrator-approved routes, **not** evidence that those routes exist.

## Reuse / dependencies
- Command Center: canonical Portal/Core read models; current tenant ACL and exact endpoint contracts UNKNOWN.
- Observability: reuse qualified Grafana/Prometheus links/panels only after source, authorization and provenance verification; no synthetic metric shown as LIVE.
- Incident/ITSM: GLPI remains authority after qualified tenant-scoped read contract; no fabricated ticket IDs.
- AI Decision: Analyst/Critic citations and policy/HITL must be independently verified; no execution affordance.
- Operations Control: Temporal/Worker/Policy authority and fencing remain server-side; this navigation has no action capability.
- DemoCenter: explicitly DEMO/REPLAY with scenario provenance; no claim of production evidence.
- Twin: adapt qualified dependency graph behind canonical service/CI contract, not an invented live graph.

## Safety contract
`resolveV30Presentation` **never renders LIVE**: caller-supplied `liveAttested` and `tenantAuthorized` flags are untrusted presentation inputs, not authentication or attestation. Even when both are `true`, mode `LIVE` resolves to `UNKNOWN / UNVERIFIED` with `live: false`. A future LIVE implementation requires a reviewed server-side tenant-scoped authorization and provenance contract, plus dedicated integration tests; no such contract is implemented in this PR. Missing/contradictory mode yields UNKNOWN/UNVERIFIED. DEMO and REPLAY always remain non-LIVE. The static anchors do not enable LIVE actions.

## Qualification / handoff
Run `node --test app/portal/components/v30_safe_navigation.test.mjs` on the exact PR HEAD. Then architect must connect actual routes, test 320/768/1440 px keyboard/screen-reader focus and WCAG contrast, verify tenant isolation, CSP, Grafana/GLPI/Twin contracts, LIVE fail-closed API, and browser screenshots at exact SHA. **Browser, runtime, connector and Debian tests: UNKNOWN.** A standalone component is not a finished V30 experience.

**Integration decision:** HOLD until the architect reconciles #703/#557/#705 and identifies the approved V30 route surface. Rollback: revert this PR (or omit its import); no persistent state is changed.
