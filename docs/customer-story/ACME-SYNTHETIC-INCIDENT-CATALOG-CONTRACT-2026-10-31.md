# ACME — deterministic graph-bound SYNTHETIC incident catalog (contract v1)

Scope: ACME/Twin 1/5, **offline fixtures and contracts only**. Source of truth: main, PR #195 architecture/reuse register, PR #201 staging, issue #186. This is **not** a second Core/ITSM/Temporal/Twin engine. No network, GLPI write, SSH, sudo, deployment, HITL approval, real observation or LIVE action.

## Reuse inventory (reviewed before implementation)

- Authoritative topology: db/migrations/005_seed_acme.sql, Git blob 67f0124a2c3b450e5249165e719a5d943fdd7237; 18 CIs, 17 edges, 4 registered scenario IDs, 7 Golden Payment steps. The older 003_seed_twin.sql and app/portal/acme-fixtures.json use **different** identifiers and must not be joined.
- Existing simulator: app/simulator/main.py owns /api/scenarios, /api/launch and /api/demo/golden; its launch route **writes** Core incidents/runs and is intentionally not called here.
- Existing Twin: app/twin/main.py exposes graph/impact. Its current impact SQL follows source_id→target_id (consumer→dependency), not a qualified reverse dependent traversal. This offline contract calculates **candidate** reverse blast radius without changing the Twin service.
- Existing locator: PR #198 tools/find_acme_demo_run.py and its isolated tests, read-only and fail-closed until authenticated Core Run/Evidence reads exist.
- Historical divergent PR #185, reviewed only: tools/generate_acme_telemetry_v291.py provides seeded-random synthetic telemetry, tools/generate_acme_adversarial_v294.py separates synthetic observations from evaluation-only truth, and tools/probe_acme_twin_path.py documents reverse traversal. Reused design patterns and the main seed, **not** the divergent tree or historical IDs.

## Dataset and safety contract

The catalog tests/fixtures/acme_enterprise_incident_catalog_v1.json declares 10 enterprise categories with severity P1–P4, urgency, frequency, duration, blast radius, maintenance window and recovery semantics. Four are replayable against existing CIs: redundant SAN path loss (the **only** customer SAN→Payments story), network failure, storage capacity pressure and application degradation. Six are **BLOCKED_MISSING_CMDB_CI**: SAN controller, datastore, database, certificate, backup and cloud dependency. No substitute CI/edge is invented. Seed-registered scenario IDs are reused where available; otherwise scenario_id=null.

The offline generator tools/generate_acme_incidents.py verifies both the exact SQL Git blob and the reviewed catalog Git blob (`78e749c623d7ee7ea1d33a74577b4f7b696f3207`), rejects duplicate/invalid catalog references and computes graph-dependent service **candidates** by reverse traversal. A schema-valid but unreviewed change to urgency, severity, CI, maintenance window, or even whitespace now fails closed before replay; updating the catalog requires an explicit reviewed blob-pin change and regenerated replay/test hashes. This pin is a source-integrity contract, **not** a signature or runtime attestation. It never contacts APIs. Caller-supplied parsed `graph` and `catalog` overrides must now match the pinned on-disk fixtures exactly; changing a CI dependency or urgency in memory is rejected rather than used to fabricate a path or P1. The two adversarial tests pin the Golden Payment `dataset_sha256=ce0aef74222699da695c2e894e622b0625c992ef654dda34a84cff26b5e64f3f`, so the seven-event replay remains byte-identical. The Golden Payment story replays the **seven exact SQL steps** at offsets 0, 15, 30, 45, 60, 90, 110 seconds from the explicitly **simulated** clock 2026-10-31T09:42:00Z. Seed 20261018 is deterministic. Other graph-bound categories permit declared-seed stochastic variation; the golden story cannot be jittered.

Every event includes source, fixture-only SYN-EVT source_event_id, simulated observed_at and known_at, event_time, freshness=SYNTHETIC_CLOCK_ONLY, provenance=SYNTHETIC_FIXTURE, tenant_scope=UNKNOWN, tenant_id=null, CI ID, dedupe_key and correlation_key. These local keys are **not** authenticated Core/Evidence identifiers and never qualify cross-tenant ingestion. Incident, Run, GLPI ticket and Evidence IDs remain null/empty until verified via authoritative APIs. All six lifecycle checkpoints (GLPI ticket, Core Incident, Core Run, Evidence, resolution, reopen) are NOT_EXECUTED; publishable_to_core_or_glpi=false and live_effects_authorized=false.

### Offline correlation trust boundary

`correlate_offline` is an illustrative, **non-publishable** dedup/correlation projection. It now fails closed on unknown CIs against the pinned SQL graph, untrusted source/fixture ID authority, a non-null Evidence ID, claimed observed impact, non-synthetic freshness, invalid UTC chronology or stale simulated timestamps. Adversarial tests cover those rejections. This guard **does not authenticate** an event, prove that a synthetic payload is genuine, establish a tenant, or replace Core's signed ingest/idempotency contract. In particular, local `SYN-EVT-*`/`SYN-CORR-*` values must never be promoted to Core Incident/Run/Evidence/GLPI identifiers. No API integration or lifecycle checkpoint has been executed.

### Strict golden replay consumer contract

Consumers presenting the **one** SAN→Payments story must call
`correlate_golden_manifest_offline(manifest)` rather than treating
`correlate_offline(events)` as a source-of-truth check. The strict helper
regenerates the golden story from the pinned SQL graph, reviewed catalog and
canonical seed `20261018`, then compares the **entire** manifest before deduplication.
A plausible `SYN-EVT-*` ID, modified maintenance flag, changed service/CI,
forged GLPI/Core/Run/Evidence link, claimed ITIL P1 confirmation or fabricated
checkpoint fails even if the caller recomputes `dataset_sha256`.
The existing loose event-only helper remains for illustrative dedup testing;
it does **not** authenticate source events and must not be used for release
evidence or canonical ID correlation.

The strict helper does not authenticate any API or tenant and cannot prove
that a source event happened. `tenant_id`, `incident_id`, `run_id`,
`ticket_id` and `evidence_ids` remain UNKNOWN until independently read
from authoritative APIs; `observed_at` and `known_at` in events are simulated
fixture-clock timestamps, not LIVE observations. All six lifecycle checkpoints
remain NOT_EXECUTED, and T1/T2 still require disposable service integration.

### Strict replay contract for other supported categories

The Golden Payments story remains the **only** SAN→Payments customer
scenario. For the other three graph-bound catalog categories (network failure,
storage capacity pressure, application degradation), consumers can call
`correlate_catalog_manifest_offline(manifest, false_positive=False)`. This
regenerates the complete replay from the pinned SQL/catalog, declared seed
and stochastic flag, then compares **every field**, including lifecycle
checkpoints, impact classification, CI, service, timestamp, and synthetic
identities. It rejects a forged manifest even when its own checksum was
recalculated. The Golden category delegates to the stricter canonical-seed
validator; no alternate Golden seed or false-positive mode is accepted.

A false-positive replay requires the caller to explicitly set
`false_positive=True` **and** to supply a matching generated manifest. The
helper never infers that mode from event payloads, never confirms priority,
and never writes to Core or GLPI. A matching replay remains **SYNTHETIC,
NON-PUBLISHABLE**: tenant/Incident/Run/Evidence/ticket references are UNKNOWN,
maintenance is a simulation, and all six lifecycle checkpoints are
NOT_EXECUTED. This is a T0 validation helper, not an API authentication,
GLPI read-back, tenant isolation, or T1/T2 integration test.

## SAN→Payments and ITIL interpretation

Stored edges point consumer→dependency. Reverse candidate path: ACME-SAN-FABRIC-A → ACME-STO-PURE01 (ACME-E08) → ACME-VM-PAY01 (ACME-E06) → ACME-APP-ORACLEPAY (ACME-E04) → ACME-SVC-PAYMENTS (ACME-E02) → ACME-BIZ-PAYMENTS (ACME-E01). Fabric B remains reachable via ACME-E09. SAN-A also has a candidate ERP dependency via ACME-E16,E15,E14. **Neither an edge nor a confidence score is observed business impact; redundancy and causality remain unqualified.**

Golden P1 is a synthetic priority candidate from graph criticality and scenario urgency; impact/urgency are not measured by Core. N1, N2, N3 and incident commander are planned roles, not authenticated assignments. The seeded 92ms/OK VERIFY is not an independent recovery receipt; final SAN state remains DEGRADED. Maintenance and false-positive fixtures suppress escalation; stale timestamps never become live freshness.

## Reproduction / artifact

From repository root, without any service or credentials:

    python -m unittest discover -s tests -p 'test_acme_synthetic_incident_catalog.py' -v
    python -m unittest discover -s tests -p 'test_acme_san_payments_fixture_contract.py' -v
    python -m unittest discover -s tests -p 'test_find_acme_demo_run.py' -v
    python tools/generate_acme_incidents.py --scenario REDUNDANT_SAN_PATH_LOSS --seed 20261018 --output /tmp/acme-synthetic-replay.json
    sha256sum /tmp/acme-synthetic-replay.json

The Quality workflow runs the new isolated tests and uploads an **offline-only** replay JSON with SHA256, not a Core Evidence artifact. dataset_sha256 hashes the canonical JSON payload without its own checksum field. Identical seed + graph + catalog produces byte-identical replay.

## Blockers / owner handoff

3/5 and 5/5 must qualify, on **disposable** PostgreSQL/GLPI/Core/Temporal/Evidence only: authoritative tenant/actor binding, GLPI readback, exact Incident↔Run↔Evidence links, source/observed_at/known_at/freshness, idempotent ticket/incident creation, dedup, cascade, tenant isolation, independent verification and resolution/reopen. Current results qualify **T0 offline fixture contracts only**, not T1/T2 E2E, Debian, production or LIVE. RELEASE_STABLE=NO_GO.
