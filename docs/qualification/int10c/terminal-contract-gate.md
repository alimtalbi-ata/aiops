# INT10-C4 — B/C terminal contract gate

## Verified source
B handoff #804 comment 6985831779 defines Core #234 `terminal_reject(tenant_id,event_id,payload,authorization)` with exactly eight JSON body keys: owner, run_id, proposal_id, proposal_hash, proposal_revision, lease_token, execution_allowed, effect_allowed. No incident_id or attempt_id exists on that wire. Terminal requires permission, expired lease, attempts >= 8, matching tenant/owner/token/run/proposal/hash/revision, and atomically returns DEAD plus immutable receipt. No new readback API is assumed.

C's existing `app/worker/hitl_reject_terminal_runtime.py` instead calls token-free `terminal-recover` and `terminal-receipt`, and its request includes incident_id. It therefore does NOT implement B's `terminal_reject`. Its current helper must not be represented as a B adapter or activated against B.

## Gate
- Keep negative terminal_reject separate from positive Core resolve.
- No inferred incident/attempt join, invented endpoint, altered body key, or token substitution.
- Preserve UNKNOWN/UNBOUND for missing joins and source authority.
- Await explicit architect decision on a distinct adapter and any independently evidenced association before code changes.
- Until then, existing helper remains isolated/injected and offline only.

## Qualification
This increment adds a static regression guard for the incompatibility and accidental invocation. It does not qualify terminal DB atomicity, permission enforcement, expiry, receipt persistence, tenant isolation, network, or Temporal. RT10 NO-GO.
