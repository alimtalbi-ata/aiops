# Runs/Evidence late response guard — isolated read-only contract

Scope: pure failure-only settlement helper, stacked on #640 in the #547→#550 transport chain. It never returns records, evidence or READY. It is **not wired** to a live endpoint.

Server-side adapter MUST mint monotonic safe-integer generation and activeGeneration per authorized request scope, and terminal cancelled/timedOut booleans. Never use browser, JSON, query, headers, or caller-supplied generation/actor/tenant as trust anchors. Server actor/tenant authorization must precede any read projection. No qualified ACL means UNKNOWN and blocked bootstrap/components/copilot/demo (TENANT_ACL_NOT_QUALIFIED).

Decision order: malformed/missing/accessor/proxy descriptor -> ERROR/READ_FAILED/null; older/different generation -> UNKNOWN/STALE_RESPONSE/null; cancellation -> UNKNOWN/CANCELLED/null; timeout -> UNKNOWN/TIMEOUT/null; current otherwise -> UNKNOWN/NOT_QUALIFIED/null. Returned objects are frozen. A separate authorized projector must check tenant scope, provenance, observed_at freshness, schema and budgets before READY. This guard alone is **not** a security boundary against fabricated server transport signals.

Tests: `node --test app/portal/components/read_settlement_guard.test.mjs`. Negative cases: stale response with forged READY/payload, simultaneous terminal flags, 200/fresh/authorized claims, malformed types, inherited values, accessor and throwing Proxy. Tests are committed, not asserted executed.

Controlled isolated recipe: review #545/#555 and #547→#550; run Node tests at exact SHA; check SHA-specific CI including existing quality-gate failure; simulate overlapping reads, late replies, cancel/timeout, 401/403, cross-tenant denial, missing/stale provenance and no READY promotion; record expected/actual, timestamps, SHA, reviewer and CI URLs. Do not treat unit tests as E2E or Debian evidence. Rollback: discard draft branch; no live rollback needed.

No merge, deployment, Debian stack, runtime, cron, GLPI, PG, Policy/HITL, Core/Worker/Twin changes; no external DNS.
