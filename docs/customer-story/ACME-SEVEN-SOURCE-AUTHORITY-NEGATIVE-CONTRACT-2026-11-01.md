# ACME SAN→Payments — seven-source authority negative contract (2026-11-01)

**Status: SYNTHETIC / OFFLINE_ONLY / UNAVAILABLE.** This is a fail-closed
fixture projection, not an authenticated Core Incident/Run readback, GLPI
ticket, human approval, Evidence receipt, model output or measured impact.

## Reuse and scope

The source is the pinned migration 005 graph (18 CI, 17 edges), replay seed
`20261018`, seven immutable source events and existing
`tools/acme_synthetic_three_domain_receipt.py`. No new event store, CMDB,
Core API, Portal, Worker, Policy, workflow, database or container is created.

`tools/acme_synthetic_source_authority_negative.py` emits the redacted
`ACME-SYNTHETIC-SEVEN-SOURCE-AUTHORITY-NEGATIVE-2026-11-01.json`.
Each of seven ordered rows has an exact `source_event_id`, a canonical ACME
full-event SHA256, an ACME local-payload SHA256 and a *proposed* schema-wrapped
Core payload SHA256. These three local domains are different; none is a
persisted Core PG16 payload or full-run-event digest. The Core domains
`aiops.core-source-event-payload.v1` and `aiops.core-full-run-event.v1`
are independently owned by Core, with source receipt schema
`aiops.core-canonical-seven-source-receipt.v1`. Core's own readback
cannot be inferred from the local mapping or from equal-looking IDs.

The fixture explicitly contains `null` for both Core PG16 hash fields
on every row. Actor, tenant, Incident, Run, GLPI ticket and HITL approval
identifiers are `null`; freshness, revocation and observed impact are
`UNKNOWN`. Core readback is `UNAVAILABLE`. All **15 ITIL stages** and
**six checkpoints** remain `NOT_EXECUTED`. P1 and HIGH are synthetic
scenario estimates, not observed production impact.

## Determinism and negative cases

```bash
python -m tools.acme_synthetic_source_authority_negative --emit
python -m tools.acme_synthetic_source_authority_negative --check
python -m unittest discover -s tests -p 'test_acme_san_payments_fixture_contract.py' -v
```

The test suite compares every row against the pinned replay, rejects missing,
reordered, duplicate or foreign events, rejects swapped/forged hash domains,
foreign tenant/actor, fabricated runtime IDs, fake Core full-event hash,
and attempts to assert freshness or HITL approval. Even a passing fixture
check returns `UNAVAILABLE`, not `VERIFIED`.

## Dependency and safety

Only Core/identity can provide independently actor+tenant-authorized PG16
seven-event readback with exact persisted serialization, immutable audit
013/014, freshness, revocation and native human GLPI permission. Until
then there is no authority to promote any Incident/Run/GLPI/Evidence binding.
No network, host, SSH, Docker, persistent stack, GLPI write, LIVE remediation,
deployment, or portal port claim is involved. TCP 7777 is the desired host
entrypoint but remains NOT_VERIFIED; 17777 is a different port.

Rollback: revert only the focused source-branch commits touching this
ACME tool, the ACME fixture contract tests, and these customer-story files;
architect alone integrates. `RELEASE_STABLE=NO_GO`.
