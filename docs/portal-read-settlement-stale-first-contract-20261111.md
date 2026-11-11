# Runs/Evidence settlement: stale-first contract (2026-11-11)

Parent: Draft #644; integration #555; handover #545; transport #547 → #550. Offline pure helper only, no live wiring.

## Invariant and trust boundary
Validate server-minted `generation` and `activeGeneration` as nonnegative safe integers first. If different, return frozen `{state:'UNKNOWN',reason:'STALE_RESPONSE',result:null}` without reading `cancelled` or `timedOut`. This prevents superseded requests with missing/hostile terminal fields from hiding the stale outcome. For matching generations, require own data descriptors and strict booleans, then apply CANCELLED > TIMEOUT > NOT_QUALIFIED. Malformed generations or current terminal fields fail closed with `ERROR/READ_FAILED/null`. No READY and no payload.

Actor/tenant and generation provenance must be derived and scoped server-side; never trust browser, response body or query/header assertions. HTTP status, authorization, provenance and freshness are separately qualified; this helper cannot authorize reads. Unqualified bootstrap/components/copilot/demo remain blocked (`TENANT_ACL_NOT_QUALIFIED`).

## Negative tests and controlled recipe
Run at exact HEAD: `node --test app/portal/components/read_settlement_guard.test.mjs app/portal/components/read_settlement_stale_first.test.mjs`. Cases: stale hostile accessors, stale missing terminal fields, current hostile/missing terminal fields, malformed generation. Re-run transport diagnostics suite and cross-tenant 401/403, cancellation/timeout, late response, stale observed_at, missing provenance, forged READY claims in isolated authorized candidate. Record SHA, test outputs, CI conclusions, reviewer, source timestamps and expected/actual. No E2E or Debian claims from offline tests.

## Gates
NO_GO until tests and SHA-specific CI succeed, independent server ACL qualification and reviewer approval. Rollback: discard this isolated Draft branch, leaving #644 unchanged. No merge, deployment, runtime, cron, GLPI, PG, Policy/HITL, Core/Worker/Twin or Debian modifications. No external DNS.
