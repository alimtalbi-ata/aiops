# V2.7 — Qualification gates before any deployment (2026-10-20)

**State: GitHub candidate only; NO-GO for operational promotion.** Preserve the qualified V2.6 lab, the operational aiops2-rebuild stack, and all previously validated UI ports.

## Source scope
- PR #34, branch `feat/worker-v27-denial-reconciliation-20261020`.
- Migration: `db/migrations/090_critic_denial_outbox.sql`.
- Core: `/denial-intent`, `/denial-intents/pending`, `/reconciled`.
- Worker: `durable_denial_intent` and `reconcile_denial_batch`.
- Unit contracts: `tests/test_v27_denial_reconciliation_fail_closed.py`.

## Safe first test (no Docker required)
On a checked-out candidate revision in a separate working tree:

```bash
python3 -m unittest discover -s tests -p 'test_v27_denial_reconciliation_fail_closed.py' -v
python3 -m py_compile app/core/main.py app/worker/main.py
```

The tests use Python AST extraction and fake HTTP dependencies. They do **not** touch Debian, Temporal, PostgreSQL, Policy, GLPI, or real endpoints. They cover denial persistence order, unexpected Policy PASS, unexpected decision, Policy outage, Core persistence outage, and ACK outage. They are **unit contract tests**, not E2E acceptance evidence.

## Isolation and acceptance gates
1. Verify rootless Docker owner; independent lab project, volumes, networks, and no published ports; no production DB or API credentials.
2. Backup isolated lab DB; explicitly apply SQL 090 to existing isolated DB and validate tables/constraints. Entrypoint migrations are not rerun on an existing volume.
3. Build **both** candidate Core and Worker from an exact commit, use tagged images in isolated compose, test API and migration together.
4. Fault injection: stop only *lab* Policy; rejected Critic and Core BLOCK must be recorded; outbox remains PENDING; zero HITL/REMEDIATE.
5. Restore lab Policy; after reconciliation only BLOCKED Policy verdict is persisted, linked to matching analysis and Critic; outbox becomes RECONCILED, no effect stage.
6. Concurrent workers, conflicting nonce/replay, crash between Policy record and ACK, Core failure before intent, and Worker restart.
7. Assert no duplicate policy decisions, no fail-open, and durable audit across interruption. Review uniqueness on policy input hash, leases/fencing and atomicity.
8. Preserve evidence: Git SHA, migration SHA256, test stdout, Temporal final states, Core ledgers, DB outbox status and read-only deployment diff.

## Open blockers (P0)
- Intent creation and terminal BLOCK are **not atomic**; a Core outage can leave neither durable intent nor recorded terminal status.
- Pending scan lacks worker lease/fencing; multi-worker races unqualified.
- Direct Policy write and reconciler can race; input-hash uniqueness and idempotent replay require database constraint and E2E proof.
- Outbox lacks bounded retry/dead-letter policy and metrics.
- HITL identity binding and any LIVE execution gate remain outside V2.7 qualification.
- The operational metrics normalizer and Grafana dashboard are a separate qualified demonstration setup, not V2.7 acceptance.

**Promotion rule:** No merge to main or replacement of V2.6 until every P0 acceptance item above has recorded PASS evidence.
