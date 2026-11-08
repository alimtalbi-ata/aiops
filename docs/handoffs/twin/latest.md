# Twin #460 — source fixture qualification

UTC: 2026-11-08T16:55:38.476382+00:00
Issue: https://github.com/alimtalbi-ata/aiops/issues/460
Role: Twin
Branch: `agent/twin/460-scenarios`
Tested code SHA: `4d7586c3b1ec0298684fc4ca42fe07d889520c6a` (documentation-only follow-up adds this handoff).
Reusable prerequisite: PR #453 at `d99f552a2e48b9dcdd0bbda585e1d1339c670576`.
PR target: pending Integration confirmation; stacked target proposed: `feat/fs147-twin-adapter-qualification-20261108`. No existing agent branch modified.

## Changed paths / ownership

- `tests/test_fs147_twin_replay_460_contract.py`: five additive tests using existing FS147 adapter/provenance fixtures unchanged.
- `docs/handoffs/twin/latest.md`: Twin-specific evidence and blockers.

No Core, Worker, Portal, Integration, shared canonical docs, migrations, runtime configuration or CI workflow changed. Interface touched: fixture-only `qualify_pair` and `reject_foreign_provenance`; no API contract added.

## Discovery / reuse

Read AGENTS.md and orchestration, continuity, component catalog and reuse inventory on `ops/aiops2-multiagent-orchestration-20261108`. Read issues #457–460 via public GitHub HTML, including #457's handoff linking #453. Queried open Twin PR list; discovered #453, #424, #421, #405, #384 and #366. Inventory is scoped discovery, not full qualification of every historical PR.

All remote heads fetched; enumerated Twin-related branch trees and exact SHAs. Actual candidates inspected:

| Source | Exact SHA | Actual paths / disposition |
| --- | --- | --- |
| `feat/fs147-twin-adapter-qualification-20261108` (#453) | `d99f552a2e48b9dcdd0bbda585e1d1339c670576` | `tests/test_fs147_twin_adapter_boundary_contract.py`, `tests/test_fs147_twin_nested_provenance_contract.py`, isolation test. Reused unchanged. |
| `test/fs147-twin-san-isolation-20261107` | `2a3fa9f86684564920a1cda92c47cbe074e40c5c` | `tests/test_fs147_twin_san_isolation_contract.py`. Predecessor, already included by #453. |
| `feat/acme-san-scenarios-provenance-20261103` (#366 candidate) | `cec48fa2a0e5976be90d3cebcdf929d05835a58f` | `app/twin/acme_san_scenarios.py`, exact migration-019 topology and read-only scenarios. Not ported. |
| `fix/fs-1009-twin-decimal-metrics` | `50466734c629840e8852c36c3e6a9a14e19d0076` | `app/twin/fs_observations.py`, real FS evidence ingestion and metric adapter. Not ported; no real evidence accessed. |
| `twin/t2-synthetic-contract-20261105` (#424 candidate) | `322023d61eb9debea9078a2256629887a091d862` | `tests/test_twin_synthetic_runtime_isolated.py`, AST-extracted synthetic handler with fake DB. Not real PostgreSQL or E2E. |
| `deploy/aiops2-stable` | branch inspected, not qualified | `app/twin/acme_sandbox.py`: signed sandbox approval with independent Core readback. Not connected or executed here. |
| `main` | branch inspected, not qualified | `app/twin/main.py`: canonical graph/impact and synthetic-event routes. Not rewritten. |

These are distinct layers; FS147 fixture validation does not prove deployment of the real evidence adapter or sandbox API compatibility.

## Tests actually executed

Python 3.12.14, existing checkout; no dependency installation, service startup, Docker or network needed for this suite.

`python3 -m unittest discover -s tests -p 'test_fs147_twin*contract.py' -v`

- Baseline: 25 tests PASS.
- With this change: 30 tests PASS, zero failures/errors/skips.
- Five new tests cover alternating repeated JSON deliveries without input mutation; rejection followed by clean SAN/FS replay; shared observation object rejection in both directions; independent equal observations accepted; duplicate foreign provenance rejected.
- `git diff --check`: PASS.

Duplicate-event limitation: equality of separately decoded JSON observations is accepted by the existing provenance validator. Shared Python object references are rejected, but that is not durable event deduplication. These tests deliberately preserve that distinction.

## Dependencies / explicit blockers

- #458 Core and #459 Worker: provide canonical FS147/FS1250 read-only lineage, event identity/idempotency contract, duplicate/concurrent delivery persistence semantics and evidence receipts. Required to test exactly-once effects; no substitute implementation added in Twin.
- #457 Integration: arbitrate PR base and CI registration. Existing quality workflow explicitly selects tests and does not select this FS147 glob; no claim that remote CI runs these tests automatically.
- Git read and branch push work through existing authentication. API reads via both `gh issue view` (GraphQL) and `gh api` (REST) return Forbidden at `api.github.com`. Public GitHub HTML is readable but unauthenticated; no write credentials extracted or invented.
- Environment draft read/update returned INVALID_ARGUMENT; requested `api.github.com` domain addition is NOT confirmed saved. Required next action: enable this domain in environment settings, retain existing domains/presets and existing GitHub authentication; verify API access before retrying publication. A present GH_TOKEN binding alone does not prove API access.

## Gates / runtime evidence

CODE: committed and branch pushed; additive fixture coverage PASS.
CI: NOT_VERIFIED at this change's exact SHA; no run URL claimed.
DEBIAN: UNKNOWN; no host access or fresh receipt collected. Prior #457 comment is historical evidence only.
E2E: NOT_VERIFIED. No independent event→Core→Critic→Policy→Worker→Evidence→Portal→ITSM verification performed.
FS1250: HOLD.
No deployment, GLPI/PG writes, cron/Compose changes, merge or Policy/Critic/HITL bypass.

Risks: synthetic fixture coverage only; depends on unmerged #453; observation deduplication and real data schema compatibility remain unqualified. No production effect. Rollback: revert the isolated test commit and this handoff.
Next owner: Integration for API access/base/CI; Core and Worker for lineage/idempotency evidence; Twin resumes isolated integration after prerequisites exist.
