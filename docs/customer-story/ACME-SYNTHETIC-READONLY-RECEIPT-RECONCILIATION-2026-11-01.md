# ACME — Offline fixture-to-Core receipt reconciliation (2026-11-01)

**Status:** SYNTHETIC contract / P1 source-only / **not** runtime proof. No API call, tenant authentication, GLPI mutation, model invocation, HITL approval, simulation, host action, or deployment.

## Source and immutable boundaries

The verifier `tools/acme_synthetic_receipt_reconciliation.py` composes the existing `verify_itil_replay_offline()`, which in turn reuses the canonical seven-event ingestion preflight and pinned 005 Twin. No second Incident Store, CMDB, Portal, Evidence ledger, workflow or synthetic event generator is created.

- Scenario `SCN-GOLDEN-PAYMENT-P1`, seed `20261018`, **7 events**.
- Pinned graph `db/migrations/005_seed_acme.sql` Git blob `67f0124a2c3b450e5249165e719a5d943fdd7237`: **18 CI, 17 edges**.
- SAN-A → Pure01 → PAY01 → OraclePay → Payments, edge IDs `ACME-E08,E06,E04,E02`.
- Canonical replay JSON SHA256 `bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8`.
- Event source hashes are **not** Evidence-service receipts; test partitions are **not** authenticated tenants.
- Reverse-reachable ERP/Payments are only **blast-radius candidates**; HIGH is estimated, P1 is not confirmed.

## Read-only reconciliation rules

`reconcile_fixture_receipts_offline(manifest)` returns 15 ITIL stage requirements and six runtime checkpoints. Each stage has a pinned source-event anchor and the authority needed to verify a real receipt. **All 15 stage statuses and six checkpoints are `NOT_EXECUTED`; all receipt IDs are null, and all source/authority outcomes remain `UNKNOWN`.** This is not a successful Core readback.

A separate `synthetic_absence_envelope_offline(verified)` can exercise the envelope validator with synthetic, empty fields and a fixture-relative UTC clock. It has `source=OFFLINE_TEST_INPUT_NOT_CORE`; it is not an API response. The validator rejects foreign partitions, forged replay/source/CI/service, missing or extra fields, stale or premature clocks, and *any* non-null Incident, Run, GLPI, Evidence or stage receipt. It never trusts a caller-supplied `verified=true` claim.

A future independently authenticated, tenant-isolated **read-only Core/GLPI/Evidence adapter** must supply the actual source responses, immutable evidence digests, authority checks, freshness, and shared incident/run/service/CI/ticket bindings. Until that adapter exists, this module deliberately cannot elevate untrusted input into an executed stage. Do not substitute titles, copied IDs or synthetic event IDs for runtime identifiers.

## Stage-to-authority contract

| Stage group | Required authority |
|---|---|
| Event/Alert | Pinned synthetic source event (not an Incident receipt) |
| GLPI ticket | Authenticated GLPI readback |
| Core Incident / Run | Authenticated Core readback |
| Twin candidate impact | Governed Twin dependency graph |
| Analyst / Critic | Core immutable AI ledger and sourced model outputs |
| Evidence | Immutable Evidence service |
| Policy proposal | Core Policy ledger |
| HITL approval | Core verified-human decision ledger |
| SIMULATE | Isolated executor effect receipt |
| Post-action verification | Independent postcondition evidence |
| Resolution / Reopen | Core Incident lifecycle ledger |
| Problem / Knowledge / Change | Governed ITSM and Knowledge authorities |

These are **requirements**, not observations or assertions that the corresponding actions happened. No observed SLA/OLA, owner, Change ID, maintenance window, approved P1, analyst output, effect, resolution or reopen is inferred.

## Reproduce and rollback

```bash
python -m unittest discover -s tests -p 'test_acme_synthetic_incident_catalog.py' -v
python -m unittest discover -s tests -p 'test_find_acme_demo_run.py' -v
python -m unittest discover -s tests -p 'test_acme_san_payments_fixture_contract.py' -v
python -m unittest discover -s tests -p 'test_acme_fixture_override_types.py' -v
```

The new 11 adversarial tests live in the already-discovered catalog suite. No shared Quality workflow change. Revert only the three ACME-owned paths of this focused PR; preserve the canonical replay, pinned SQL graph, and the architect's sole candidate #234. Runtime gate remains `RELEASE_STABLE=NO_GO`.
