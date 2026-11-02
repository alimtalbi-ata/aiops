# ACME — future Core actor/tenant/source-hash binding, fail-closed (2026-11-01)

**P1 source-only, synthetic contract.** This is a validation interface for a *future* independently authorized Core Incident/Run readback, not a Core API, tenant identity service, receipt store, authenticated session, model inference or customer observation. It never calls Core, GLPI, Evidence or an executor. No schema/migration/Portal/Worker/shared workflow change.

## Pinned source and reproducibility

- Sole ACME SAN→Payments canonical replay: `SCN-GOLDEN-PAYMENT-P1`, seed `20261018`, seven SYNTHETIC events, JSON SHA256 `bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8`.
- Graph 005 pinned Git blob `67f0124a2c3b450e5249165e719a5d943fdd7237`, 18 CI/17 edges. SAN-A → Pure01 → PAY01 → OraclePay → Payments via `ACME-E08,E06,E04,E02`. Reverse-reachable ERP/Payments are **CANDIDATE** impacts, not observed outages.
- `tools/acme_synthetic_future_core_binding.py` reuses `acme_synthetic_itil_replay_verifier` and derives seven per-event SHA256 digests from `gen._canonical(event)`, each paired with its exact source event ID, CI, event time, dedupe and correlation key. These are content digests, **not immutable Evidence receipts**.
- A proposed shape must match all seven records in order and the pinned scenario, service, CI, graph version, dataset/manifest/replay digests, correlation and clock. Foreign partition, mismatched actor/tenant on either Incident or Run, stale/future readback, extra/missing fields, forged authority, live-looking IDs and altered seed fail closed.

## Authority boundary

The only accepted proposal source is `OFFLINE_TEST_INPUT_NOT_CORE`. It requires clearly `TEST_ONLY` placeholders, not real IDs, and an explicit `UNVERIFIED_TEST_INPUT` attestation with all authority booleans false. This enables adversarial unit tests of the *shape* without creating fake Core/GLPI tickets or asserting a real authorization. A shape match returns **`result=UNAVAILABLE`**, not VERIFIED, and **does not return the test placeholders as runtime references**. Without a proposal, `reason=CORE_INDEPENDENT_ACTOR_TENANT_AUTHORITY_UNAVAILABLE`.

The future Core/identity owner must independently supply and review:

1. authenticated actor identity and server-side tenant ACL (including revocation);
2. a signed or equivalently trustworthy readback binding the *same* tenant and actor to Incident and Run, with independent authorization;
3. all seven immutable source-event content hashes, event IDs, dedupe/correlation keys and CI/service/graph version, tied to that pair;
4. bounded readback freshness, audit provenance and rejection of cross-tenant/foreign/missing/stale claims.

**Do not use caller-supplied tenant fields, synthetic partitions, a service Bearer or an apparently matching scenario name as independent authority.** The ACME owner does not implement or invent the Core authority; Core/identity must publish its actual schema, verification and disposable E2E evidence before any promotion is considered. GLPI ticket, Evidence, Analyst/Critic, Policy/HITL, SIMULATE and post-action receipts require separate sources.

## Reproducible offline check

```bash
python -m unittest discover -s tests -p 'test_acme_synthetic_incident_catalog.py' -v
python -m unittest discover -s tests -p 'test_find_acme_demo_run.py' -v
python -m unittest discover -s tests -p 'test_acme_san_payments_fixture.py' -v
python -m unittest discover -s tests -p 'test_acme_fixture_override_types.py' -v
```

No endpoint, token, host or GLPI write is needed. All 15 ITIL stages and six runtime checkpoints remain **NOT_EXECUTED**; tenant/actor/Incident/Run/GLPI/Evidence IDs are `UNKNOWN` or null, priority P1 is a candidate, HIGH is estimated, observed impact `UNKNOWN`, SLA/OLA and actual maintenance/change authority `UNKNOWN`. The test partitions are not authenticated tenants.

**Dependency:** independently actor+tenant-authorized Core readback, with source hash bindings and verifiable audit/freshness, on a disposable instance. **Rollback:** revert only the new ACME tool, added catalogue tests and this document on the focused source branch. Architect alone may selectively integrate into Draft #234 after exact-head CI. `RELEASE_STABLE=NO_GO`.
