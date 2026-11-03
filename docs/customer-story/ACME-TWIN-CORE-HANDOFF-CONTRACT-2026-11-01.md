# ACME/Twin — executable seven-event Core payload and impact handoff (SYNTHETIC)

**Scope:** ACME-owned source-only Draft, disposable CI, no runtime side effects. Reuses canonical seed `20261018`, pinned `005_seed_acme.sql` graph (18 CI / 17 edges), seven `SYN-EVT-*` source events, existing three local SHA256 domains and existing 15-stage/six-checkpoint ITIL plan. Does **not** re-port prior ACME work or create a second Incident Store, CMDB or Portal.

## Executable integration boundary

`tools/acme_synthetic_pg16_twin_impact_handoff.py` exposes two pure functions:

- `disposable_core_payloads(manifest, scope)`: validates the entire canonical ACME replay, requires **five distinct caller-supplied `TEST_ONLY_*` identifiers** (tenant, Incident, Run, ticket, entity), and creates seven Core-domain **proposed** payloads with `source_event_id`, sequence, source CI/action/time and the Core `aiops.core-source-event-payload.v1` digest. It never inserts rows, allocates IDs, authenticates actors, grants GLPI rights, computes a persisted full-event hash or calls an API. Core owns actual PG16 inserts and its independent readback.
- `build_preview(manifest, core_readback=...)`: combines the already pinned seven-source hash receipt, correlated local incident **candidate count 1**, and reverse dependency path SAN-A → Pure01 → PAY01 → OraclePay → Payments into an API-neutral, redacted **synthetic preview**. It reuses the existing fail-closed Core intake gate; caller-supplied portable Core JSON, matching bytes, claimed 013/014 audit, revocation or HITL approval never become authenticated authority.

The selected dependency path is backed by edges `ACME-E08,E06,E04,E02`, with candidate blast radius 10 CIs, Payments and ERP candidate services, estimated impact HIGH and proposed P1. These are **modelled possibilities**, not observed outages, evaluated redundancy or confirmed ITIL priority. The source event `INCIDENT_OPEN` is a scripted action, not a Core Incident creation.

## Redacted machine receipt

`docs/customer-story/ACME-TWIN-CORE-HANDOFF-UNKNOWN-2026-11-01.json` pins seven source IDs and their three local SHA256 domains. It explicitly reports:

- `candidate_incident.status=NOT_CREATED`, Core Incident/Run/tenant/actor/ticket/Evidence IDs null;
- `core_readback_status=UNAVAILABLE`, Core PG16 full/payload hashes null, equivalence UNKNOWN;
- **15/15 ITIL stages NOT_EXECUTED**, **6/6 checkpoints NOT_EXECUTED**, no human GLPI ALLOW, HITL approval or LIVE effect;
- `portal_read_model_kind=SYNTHETIC_PREVIEW_ONLY` and `portal_integration_status=NOT_CONNECTED`. This is a handoff contract for the Portal owner, **not** an implemented API/route or a Debian observation.

Reproduction:

```bash
python -m tools.acme_synthetic_pg16_twin_impact_handoff --check
python -m tools.acme_synthetic_pg16_twin_impact_handoff --emit
python -m unittest discover -s tests -p 'test_acme_san_payments_fixture_contract.py' -v
```

The ten new regression tests cover pinned machine output, graph/path/blast radius, seven distinct source hash triples, disposable Core payload digest, foreign/missing/duplicate scope, altered/reordered source events, foreign/missing/reordered Core claims, byte-equality without authority, forged HITL/audit secrets and CLI replay. Existing Quality test discovery is reused; no shared workflow changed.

## Blocker for a real disposable Core PG16 vertical

The Core-owned PG16 producer at `app/core/canonical_seven_pg_source.py` is already present and its dedicated Core fixture uses `EVT-SOURCE-01..07`. The canonical ACME replay instead uses seven `SYN-EVT-*` IDs. The two datasets are **not the same readback**, even if both have seven rows. Core owner must seed the **actual seven ACME IDs** into one disposable PG16 Incident/Run using the separately supplied TEST_ONLY scope and native 001/004/009–014 migrations, then issue an independently authenticated actor+tenant readback with fresh ownership, nonrevoked grant and immutable audit 013/014. GLPI human rights, Evidence, HITL and Portal display need independent qualification. An offline JSON or SHA equality cannot substitute for these checks.

No new persistent stack or Debian action. Operator-verified local 7777 binding/health is distinct from unverified external TLS/SSO/GLPI E2E and uniqueness. `RELEASE_STABLE=NO_GO`. Rollback: revert the focused ACME source commit(s) only; preserve Core 013/014 audit and all host volumes.
