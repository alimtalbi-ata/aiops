# Remediation Lab v0.1 — design, contract and safety boundary

**Date:** 2026-10-27 · **Status:** offline source-only prototype, NOT deployed or connected to Core/Temporal/Portal/Policy. **PR:** [#42](https://github.com/alimtalbi-ata/aiops/pull/42).

## What exists

- `config/remediation/recipes.v1.json`: 8 versioned, allowlisted **metadata** recipes: Bash service inspection; Python disk diagnostic; Ansible service restart; Linux CLI status; network CLI interface inspection; DB CLI health; Checkmk API acknowledgement proposal; GLPI API ticket-note proposal. These are **not executable scripts/playbooks**. All entries are `SIMULATOR_ONLY`.
- `app/shared/remediation_lab.py`: stdlib-only catalog loader, strict typed parameter/CI prefix validation, canonical SHA-256 proposal digest, secret-reference redaction, human-decision fixture checks, deterministic idempotency key, timestamped no-effect simulation receipt.
- `tests/test_remediation_lab.py`: ten focused tests (locally passed on mirrored proposed sources). CI/runtime still unqualified.

## Contract and example

```json
{
  "proposal_id": "P-1", "recipe_id": "ansible-service-restart",
  "recipe_version": "1.0.0", "target_ci": "ACME-LNX-01",
  "parameters": {"service": "erp", "credential_ref": "vault://acme/erp"},
  "mode": "DEMO", "requested_by": "analyst-1"
}
```

`validate_proposal(proposal)` rejects unknown recipes/versions, CI prefix mismatch, missing/extra parameters, untyped IDs, invalid integer ranges and plaintext secrets. It returns recipe metadata and the hash of the **entire exact proposal**. A fixture `decision` must bind this hash, identify a distinct approver with role `approver`, carry a future UTC expiry and `authenticated=True`. **This boolean is caller-supplied test data and does not authenticate a human.** Never expose it as a production approval endpoint.

`evaluate_simulation(proposal, decision, preconditions, now=...)` returns `BLOCKED` or `SIMULATED`. Every result includes UTC timestamp, digest, version, target, redacted parameters, `effect_applied=false`, `postchecks=NOT_RUN`, `rollback=NOT_REQUIRED`, timeout budget and stable idempotency key. `SIMULATED` means only that a local fixture satisfied validation; it does **not** prove preconditions, execute a script, verify recovery or persist an effect receipt. All `LIVE` proposals are blocked **before** any simulated approval checks.

## Mandatory next implementation gates

1. **Identity:** integrate real authenticated operator identity, roles and separation of duties at Portal/Core, not user-supplied `authenticated` flags. Bind tenant, CI, action version/hash, policy version, risk and evidence snapshot to approval.
2. **Durability:** persist append-only `HumanDecision` and single-use approval receipt with optimistic concurrency, expiration, revocation, denial, replay handling and retry-safe idempotency in canonical Core/Temporal; do not build a second writer.
3. **Preconditions:** fetch actual fresh CMDB CI, ownership/fencing token, maintenance window and current evidence from authorized adapters; never accept booleans from the action requester as operational proof.
4. **Sandbox executor:** build vetted artifact paths, pinned checksums/signatures, typed argument vectors, no shell interpolation, rootless network isolation, no production credentials, resource/time limits, per-recipe rollback/compensation and no arbitrary LLM code. Initially support **read-only** Bash/Python/Ansible/CLI/API adapters; only then consider mutating sandbox fixtures.
5. **Effect verification:** record immutable source/actor/timestamp/receipt, technical and business postchecks, timeout/partial failure/reconciliation, GLPI ticket sync and Evidence Studio replay. Failed postchecks never mark Run RESOLVED.
6. **LIVE release:** separate security review, integration and failure-injection tests, backup/rollback rehearsal and explicit deployment approval. Existing Worker LIVE fail-closed behavior stays in force.

## Threat and test matrix

| Scenario | Expected |
|---|---|
| LLM supplies raw shell command or unknown recipe | Reject; no executor path |
| Recipe version/CI/parameters changed after approval | Hash mismatch; BLOCKED |
| Approval rejected, expired, forged, self-approved | BLOCKED |
| Missing/stale CMDB, fencing or maintenance window | BLOCKED |
| Secret literal supplied instead of vault reference | Reject; never log value |
| Duplicate retry | Stable key; **no durable dedupe until Core ledger is implemented** |
| Checkmk/GLPI/Ansible backend unavailable | UNKNOWN/BLOCKED; no fake effects |
| Postcheck fails | Unresolved; never auto-resolve |
| LIVE with apparently valid fixture approval | BLOCKED; unqualified |
| DEMO simulation | No side effects, postchecks explicitly NOT_RUN |

## Important limitation

This is a **typed, no-effect design and test scaffold**, not a functional Remediation Lab. Catalog metadata names Ansible/Bash/Python/CLI/API operations but ships no runnable playbooks or mutating scripts; this is deliberate until sandbox isolation, authentication, audit ledger and rollback are implemented and qualified.
