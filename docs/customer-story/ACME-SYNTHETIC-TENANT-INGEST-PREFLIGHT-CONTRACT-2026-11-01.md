# ACME synthetic tenant-partition ingestion preflight — 2026-11-01

**OFFLINE_FIXTURE_ONLY; no Core/GLPI writes.** This is a validation projection,
not a new Incident Store, adapter, runtime event, authorization or Evidence receipt.

Reuses the pinned seven-event `SCN-GOLDEN-PAYMENT-P1` replay, seed `20261018`,
18 CI/17 edges from `db/migrations/005_seed_acme.sql` (Git blob
`67f0124a2c3b450e5249165e719a5d943fdd7237`) and existing
`event_impact_contract_offline()`/vertical contract. The canonical replay
pretty JSON SHA256 remains
`bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8`;
embedded dataset SHA256 remains
`ce0aef74222699da695c2e894e622b0625c992ef654dda34a84cff26b5e64f3f`.

The two explicit `SYNTHETIC_TEST_PARTITION_A/B` namespaces are **not real
tenant IDs or authorization**. Tenant remains `UNKNOWN` and `tenant_id=null`.
Delivery envelopes carry source event bytes, pinned replay hash, local partition
and **fixture-clock** receipt time (not real ingested_at). A second identical
delivery is counted as a duplicate; missing, foreign-partition, stale, forged
source/CI/tenant/evidence/dedupe, seed or timestamp input fails closed.
Per-event SHA256 is content binding, **not durable immutable Evidence**.

The local candidate Incident is `NOT_CREATED`: incident/run/ticket IDs null,
Evidence IDs empty, no Core/GLPI writes. Reverse Twin candidate path SAN-A →
Pure01 → PAY01 → OraclePay → Payments uses `ACME-E08,E06,E04,E02`.
ERP/Payments are *candidate* blast radius only, HIGH estimated and P1 candidate;
observed impact, causality and confirmed priority remain UNKNOWN. All 15 ITIL
stages and six checkpoints remain `NOT_EXECUTED`; no Analyst/Critic, Policy,
HITL, SIMULATE or verification receipt is claimed.

Reproduce with `python -m unittest discover -s tests -p
'test_acme_synthetic_incident_catalog.py' -v`, plus existing locator, SAN
fixture and override-type suites. The existing Quality workflow already
discovers this file; no workflow edits.

**Dependency:** independently authenticated, tenant-fenced Core/GLPI readback
on disposable instances with verified Incident/Run/Evidence relationships.
Never forward local partition labels as real tenant credentials. Rollback is
revert of this focused ACME-only commit; canonical replay and architect
candidate remain unchanged.
