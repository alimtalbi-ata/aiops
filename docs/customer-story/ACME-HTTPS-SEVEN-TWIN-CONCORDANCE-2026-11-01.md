# ACME SAN→Payments — Core HTTPS seven-event source concordance (SYNTHETIC)

**Owner:** ACME/Twin only. **Scope:** source/CI qualification, not Debian or runtime authority. **Candidate:** sole Draft #234. The source consumer `tools/acme_synthetic_https_seven_concordance.py` is read-only, offline, and intentionally cannot authenticate a Core source itself.

## Executable slice

```sh
python -m tools.acme_synthetic_https_seven_concordance --check
PYTHONPATH=app:tests python -m unittest discover -s tests -p 'test_acme_san_payments_fixture_contract.py' -v
```

Nine new adversarial tests exercise **Core-owned** `core.canonical_seven_https_adapter.dispatch_canonical_seven` with an explicit **TEST_ONLY** SQL readback stub (no PG16 connection or write). They check the Core source service issuer is **not** the actor IdP issuer; Basic service credentials and trusted TLS flag are independent of actor/tenant scope. TLS false, invalid Basic, SQL exception, foreign source/actor issuer, reordered/missing/`EVT-SOURCE-*` foreign IDs, cross-tenant/Run, hash mismatch, stale/revoked and forged GLPI/HITL are negative. A test-controlled HTTP 200 only yields `CONSISTENT_UNTRUSTED`, never VERIFIED or ALLOW. No HTTP request to a host is made.

The pinned redacted receipt `ACME-HTTPS-SEVEN-TWIN-CONCORDANCE-UNKNOWN-2026-11-01.json` includes exactly seven `SYN-EVT-*` IDs, three distinct ACME-local SHA256 domains per event and null Core PG16 full/payload hashes. It retains graph 005 path SAN Fabric A → Pure01 → PAY01 → OraclePay → Payments, edges E08/E06/E04/E02 and 10 candidate CIs. Estimated HIGH/P1 is **not** observed impact. Runtime tenant, actor, Incident, Run, GLPI, Evidence and HITL IDs remain null; **15/15 ITIL stages and 6/6 checkpoints NOT_EXECUTED**.

## Core-owned next dependency and release gate

Core must first install the missing `run_events.event_key` writer migration in a **disposable PG16** environment, create one synthetic Incident/Run containing exactly these seven `SYN-EVT-*` events, then return an independently authenticated and authorized HTTPS source readback with actor IdP issuer, distinct Core source issuer, tenant/Run, full-event and payload hashes, freshness, revocation and immutable audit 013/014. The ACME comparison must be repeated against those actual bytes; matching JSON/hashes or a Core adapter 200 alone never proves actor authorization. Native GLPI human rights, HITL and real runtime execution require separate gates.

**Rollback:** revert only the focused ACME source commit(s), re-run Quality; do not touch candidate #234, Core 013/014, host, volumes, GLPI or stable. Local portal 7777 binding/health was operator-verified; external TLS/SSO/GLPI E2E and uniqueness remain NOT_VERIFIED. `RELEASE_STABLE=NO_GO`.
