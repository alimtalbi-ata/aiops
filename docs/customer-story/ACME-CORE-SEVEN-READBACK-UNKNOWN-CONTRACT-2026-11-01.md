# ACME SAN→Payments — Core seven-event readback UNKNOWN consumer (2026-11-01)

**Owner:** ACME/Twin. **State:** SYNTHETIC / OFFLINE_ONLY / UNKNOWN. **Release:** NO_GO.

This focused contract reuses the pinned migration 005 graph (18 CIs, 17
edges), replay seed `20261018`, seven immutable source-event IDs, and the
existing three-domain ACME receipt. It adds no Core endpoint, PG16 schema,
Incident/Run store, GLPI adapter, Policy, Portal, Worker, workflow, host
container or live integration.

## Machine-readable contract

`tools/acme_synthetic_core_readback_unknown_gate.py` consumes a
**caller-supplied local JSON file** in Core's informational
`aiops.core-canonical-seven-source-receipt.v1` shape. It does **not** fetch
Core or authenticate that file's provenance. It checks exact ordered source
IDs, event cardinality, separate Core payload/full-event hash-domain labels,
evidence-field presence, basic freshness syntax, and optional comparison
against a separately provided tenant/actor digest. A caller-provided expected
tenant or actor is not independent authorization. Neither a well-formed
`receipt_sha256` nor `TLS_AUTHENTICATED_NONPORTABLE` written in JSON is a
portable signature or proof that a PG16 readback occurred.

The redacted
`ACME-CORE-SEVEN-READBACK-UNKNOWN-2026-11-01.json` contains exactly seven
ordered source IDs and three **local** SHA256 domains per event: canonical
ACME full event, canonical ACME payload, and proposed Core schema-wrapped
projection. Every Core PG16 payload/full-event digest is `null`.
The supplied Core readback is `null`, and actor, tenant, Incident, Run,
GLPI ticket, Evidence, HITL and observed impact remain `UNKNOWN` or null.
No Core digest equality is asserted. Core's full-event serialization is a
different domain from ACME's full-event serialization.

Every evaluation returns `result=UNKNOWN`, with a redacted reason such as
`NO_INDEPENDENT_CORE_READBACK`, `FOREIGN_TENANT`,
`FOREIGN_ACTOR`, `MISSING_OR_EXTRA_EVENTS`,
`FOREIGN_DUPLICATE_OR_REORDERED_EVENTS`, `FOREIGN_HASH_DOMAIN`,
`STALE_FUTURE_OR_EXPIRED`, or `NO_INDEPENDENT_PG16_AUTHORITY`.
It never returns raw supplied runtime identifiers or `ALLOW`/`VERIFIED`.
The **15 ITIL stages** and **six checkpoints** remain `NOT_EXECUTED`
regardless of shape, and no runtime Evidence or verification is promoted.

## Reproduction (offline, no network)

```bash
python -m tools.acme_synthetic_core_readback_unknown_gate --emit
python -m tools.acme_synthetic_core_readback_unknown_gate --check
python -m tools.acme_synthetic_core_readback_unknown_gate --readback /path/to/operator-supplied-readback.json
python -m unittest discover -s tests -p 'test_acme_san_payments_fixture_contract.py' -v
```

The optional file must be explicitly supplied by the operator, is read-only,
is limited to 64 KiB and rejects duplicate JSON keys. The CLI emits only a
redacted UNKNOWN decision; it does not persist, echo or authorize the
supplied receipt. Disposable in-memory `TEST_ONLY_*` values used by the
adversarial tests are never fixture/runtime identifiers or Core evidence.

## Required independent authority

Core/identity owner must provide a readback actually authenticated and
authorized by actor **and** tenant, tied to the same Incident/Run and seven
PG16 events, with immutable 013/014 audit, correct canonical hash domains,
revocation/freshness, and native human GLPI rights independently checked.
Until then the Core readback is `UNAVAILABLE` and all runtime relationships
remain `UNKNOWN`. A Core source preflight success alone is not an
authorization or GLPI ticket read permission.

This PR changes ACME tools/tests/customer-story only. It neither edits the
architect's sole integration Draft #234 nor re-ports Draft #304. No
persistent stack, SSH, host Docker, volume/DB mutation, real GLPI write,
LIVE action or deploy/aiops2-stable push. Portal host TCP 7777 remains
NOT_VERIFIED; 17777 is distinct. `RELEASE_STABLE=NO_GO`.

Rollback: revert only the focused source commits on this Draft in reverse
order. Never rewrite the Core 013/014 audit or main/candidate history.
