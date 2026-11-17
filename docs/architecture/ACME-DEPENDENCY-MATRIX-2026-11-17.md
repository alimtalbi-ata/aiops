# ACME Dependency Matrix — L0 (proposal, 2026-11-17)

**Status:** PROPOSED / NOT RUNTIME-QUALIFIED. [Central tracking #804](https://github.com/alimtalbi-ata/aiops/issues/804). **Host decision:** Convergence preferred, not yet approved; Golden/#802 source of selective imports. No Debian changes.

## Ordered dependency gates

| Order | Component | Source | Evidence needed | Current status |
|---|---|---|---|---|
| 1 | Core Run, Incident, Evidence, idempotency, `acme_run_detail.py` | Convergence KEEP | contract tests, tenant ACL | BLOCKED functional |
| 2 | Receipt format + negative tests | Golden #802 ADAPT | fixture JSON + CLI rejection | This PR: proposed offline CI |
| 3 | 17-stage readiness gate | Golden #802 ADAPT | exact-SHA CI, negative receipts | Existing CI PASS on #802, no runtime |
| 4 | `/api/sandbox/acme/capabilities` | Golden ADAPT | endpoint/schema | UNKNOWN |
| 5 | Isolated E2E runner | Golden ADAPT | receipt, UTC, executed SHA | NOT_TESTED |
| 6 | `demo_v2.py` scenes | Golden SELECTIVE | one Workbench, showrun | NOT_TESTED |
| 7 | Twin / Analyst / Critic / Policy / HITL | Convergence KEEP | tenant, provenance, correlation | BLOCKED |
| 8 | Debian qualification and Portal captures | isolated after approval | 17 stages + browser 320/768/1440 | NOT_AUTHORIZED |

## JSON fixture contract

`tests/fixtures/acme/` contains 17 synthetic receipts: **one positive**, **16 negative**. Tests use fixed `2026-11-16T17:00:00Z` for determinism. The CI CLI self-check refreshes timestamps **in temporary copies only**, not the committed fixture files. No external service, Docker or GLPI is called.

Positive receipt: `schema=aiops.debian-acme-sim-e2e.v1`, `attempt_id=ACME-SIM-[A-F0-9]{16}`, `reason=SIMULATED_SANDBOX_ONLY`, `SIM-GLPI-*` ticket, `SIM-APP-*` approval, `docker_mutations=0`, and all 17 named stages PASS. Verdict **GO_SIMULATION_ONLY**, `live=NO_GO`. Each negative must exit with CLI code **2**. The tests prove gate behavior, not Debian execution.

**Known gap (P0):** The #802 validator does **not** verify an executed code SHA, cross-stage identity joins or cryptographic provenance. Those are **proposed additional contract requirements** and remain BLOCKED; this fixture-only PR intentionally does not claim to implement them.

## Selective import journal

| Component | Source SHA | Target commit SHA | Adapter | CI | State |
|---|---|---|---|---|---|
| Readiness JSON fixture suite | #802 `f594d04e02abde19b2299fbb523bf9d0d0e360b8` | See PR commits | None | Pending GitHub Actions | PROPOSED |
| Readiness gate logic | #802 same SHA | Unchanged | None | Existing offline PASS only | KEEP |
| Capabilities / runner / demo_v2 | Golden #792 / #802 | — | — | — | DEFER |

No merge into main, no LIVE authorization, no mutation of Debian or real GLPI. Decisions must be reconciled with `docs/DECISION-LOG.md` and `docs/PROJECT-CONTINUITY.md` in the same PR.

## Pydantic v2 contract (proposed in PR #805)

`scripts/acme_receipt_model.py` now declares strict `AcmeReceipt` and `AcmeIds` models with `extra="forbid"`, required stage PASS, timezone-aware freshness, synthetic IDs, and strict integer `docker_mutations=0` (rejects boolean `false`). `assess(value, now=None, max_age_minutes=60)` retains its signature and fail-closed `NO_GO` behavior. No silent fallback if Pydantic v2 is missing: CI must install `pydantic>=2.5,<3`; a future isolated runner image must explicitly bundle and verify this dependency before deployment. The gate does not access services but **dependency installation may access package registries**, so “offline” describes gate execution, not CI provisioning. Exact-SHA CI and E2E runtime remain unqualified.
