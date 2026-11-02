# ACME SAN→Payments — offline Core PG16 hash-domain comparison

**Negative-only, SYNTHETIC fixture; never an authenticated Core PG16 readback.** ACME owns the consumer, test vector and receipt. Core remains the sole Incident/Run authority and owns `aiops.core-canonical-seven-source-receipt.v1`, payload serialization `aiops.core-source-event-payload.v1`, full-run-event serialization `aiops.core-full-run-event.v1` and immutable 013/014 audit.

The separately supplied `ACME-INDEPENDENT-CORE-HASH-TEST-VECTOR-2026-11-01.json` contains seven deterministic **TEST_ONLY_UNTRUSTED_NOT_PG16** hash pairs. These are synthetic negative test bytes, not actual PG16 rows, Core API responses, portable signatures or authenticated runtime IDs. The redacted `ACME-CORE-PG16-HASH-COMPARISON-UNKNOWN-2026-11-01.json` maps the seven source event IDs to ACME full-event, local payload and proposed Core-wrapped payload SHA256 domains, and to the separately supplied test-only Core-shaped full/payload hashes. **Actual Core PG16 full/payload hash columns remain null.** All seven test-only comparisons are `MISMATCH_TEST_ONLY`; even equal test-only bytes would be `SAME_BYTES_NOT_AUTHORITY`, never `VERIFIED`.

The canonical seed remains `20261018`, pinned SQL graph `005`, replay SHA256 `bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8`, SAN-A → Pure01 → PAY01 → OraclePay → Payments. The 15 ITIL stages and six checkpoints are `NOT_EXECUTED`; no Incident/Run/GLPI/Evidence/HITL IDs, human ALLOW, measured impact, approval or effects are manufactured. Priority P1 and HIGH impact remain synthetic candidates.

Run on an isolated source checkout:

```bash
python -m tools.acme_synthetic_pg16_hash_comparison --check
python -m tools.acme_synthetic_pg16_hash_comparison --emit
python -m unittest discover -s tests -p 'test_acme_san_payments_fixture_contract.py' -v
```

Adversarial tests cover missing, foreign, duplicate and reordered source events; invalid, collapsed, duplicate or swapped hashes; foreign schema; forged actor/tenant/Incident/Run/GLPI/Evidence/HITL claims; and identical-byte false authority. Input is bounded, duplicate JSON keys are rejected and untrusted IDs are not echoed.

**Dependency:** Core/identity must independently authenticate a fresh actor+tenant-scoped seven-event PG16 readback with revocation and 013/014 audit; GLPI must independently qualify native human ticket/entity rights, and Evidence must qualify immutable tenant/Run/source binding. Offline synthetic comparisons never authorize stage transitions. `RELEASE_STABLE=NO_GO`. No Debian deployment, real GLPI write, LIVE, new persistent stack or host access.
