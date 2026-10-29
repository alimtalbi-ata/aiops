# QF-68 — Transactional denial claim

Baseline: 9885fc5
Branch: feat/v28-transactional-denial-fencing-20261020

Invariants:
- Claim only PENDING intentions belonging to BLOCKED runs.
- Claim only unowned or expired leases.
- Serialize claims using FOR UPDATE SKIP LOCKED.
- Increment fencing_token on every claim.
- Verify owner, token and lease on finalization.
- Persist Policy decision and reconciliation atomically.
- Reject legacy reconciliation without fencing.
- Never authorize remediation from a denied Critic.
- Use an isolated V2.8 qualification database.
