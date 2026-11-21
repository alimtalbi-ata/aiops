# V3 selective convergence — actual code port ledger

**2026-11-21 — PR #843, tranche 1.** This is an evidence ledger for *actual files added* and the dependencies preventing premature activation.

## Port 1 — Team C Run Journey offline projection (#824)

**Imported verbatim** from `team-c/san-payments-intelligence-20261119`:

| File | Source blob SHA | Purpose |
|---|---|---|
| `app/portal/acme_run_journey_projection.py` | `b2ae43b3cf63d2205b0da7309627b95988c7561b` | Real Python projection function `project_team_c_run_journey(impact, cockpit)`, 17 stages, deny LIVE |
| `docs/contracts/team-c-san-payments-run-journey.schema.json` | `d283d615244a868f747b9428bd543e37701ae948` | Closed v2 JSON contract |
| `tests/fixtures/team_c/run-journey.valid.json` | `605dc6595ebc56a49dbde138540b543ad89b6313` | Synthetic non-execution example |
| `tests/test_team_c_san_payments_contract.py` | `0dbc05f5e37f5c788c5c2e43da0f1274bec58959` | 12 offline positive/negative unittest cases |
| `.github/workflows/v3-selective-run-journey.yml` | New | Minimal exact-PR Python compile + offline contract gate |

**Dependency inspection on target branch `feature/mission-control-central-unified`:**
- `app/portal/main.py` exists, but does not reference `run_journey`.
- `app/portal/acme_incident_cockpit.py` and `app/portal/acme_incident_cockpit_html.py` returned GitHub 404 on the target branch. These are direct integration points used in #824/#825 and **must not be presumed available**.
- The projection function itself has no third-party imports, but its runtime inputs require `impact.twin_evidence`, `cockpit.twin_consumer`, a common `source_sha256`, `SIM-ACME-` story identity and a deterministic Analyst/Critic/Policy denial preview. **These upstream producers have not been qualified on this base.**
- The source #824 integration tests modify an existing cockpit and cannot be transplanted unchanged while the target lacks those files. The new workflow deliberately runs only the isolated contract suite, not the absent cockpit integration test.
- Source `receipt=null`, `executed_sha=null`, `tenant_id=null`, Worker `NOT_INVOKED`, HITL `SIMULATED_NOT_REQUESTED`, all 17 stages `NOT_RUN/MISSING`; never claim a real Run.

**Status:** `CODE_PORTED_ISOLATED` / `INTEGRATION_BLOCKED_BY_MISSING_COCKPIT_DEPENDENCIES`. The code is imported, but no new route, UI, real Run, Worker, GLPI, or LIVE capability is activated. Tests have **not been executed by this assistant**; CI result **UNKNOWN** until the new workflow reports on the exact head.

**Next safe step:** inspect #818 and #822 against the target at the file/diff level, then selectively port the canonical cockpit/read-model dependencies *with their tests*, or choose an existing target endpoint and adapt the projection. Do not copy #818's 92 changed files wholesale. Once upstream inputs are present, wire one read-only route, add real integration tests and require exact-SHA green CI.

## Rejected premature ports

- #799 replay/freshness test: its dependency `scripts/aiops2_event_correlation.py` is **absent on the target** (GitHub 404). Porting the test alone would break test discovery. HOLD until the canonical correlator and its dependencies are reviewed.
- #823 Playwright suite: the referenced source branch and target browser routes require verification; do not import a failing test suite without a runnable target and fixtures.
- #826/#827/#828 Twin variants: resolve supersession and same-origin contract before choosing one.
- #829 proactive Debian observer: potential host mutation/installer; HOLD pending explicit release approval and rollback qualification.

## Required before enabling this port

1. Confirm which base branch CENTRAL authorizes for V3; #843 currently targets `feature/mission-control-central-unified`.
2. Supply and validate the canonical cockpit, Twin consumer, Analyst/Critic and policy projections (or adapt to existing equivalents).
3. Run offline unittest and adversarial integration tests on the exact commit.
4. Verify that no UI claims a 17-stage PASS, approved HITL, GLPI ticket or real execution.
5. Obtain explicit CENTRAL approval before merge or deployment.

**Do not mark `INTEGRATED` or `QUALIFIED` merely because Python code and a CI workflow have been added.**
