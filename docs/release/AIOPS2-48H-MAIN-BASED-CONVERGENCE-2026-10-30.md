# 48h main-based convergence — isolated integration staging (2026-10-30)

**Status:** one draft main-based integration candidate, **NOT** a deployable cumulative release. Exact base `main@27deb9b1a66faf27df8d69b137a63451f7649d80`. No merge, stable push, Debian/runner/cron action, LIVE or GLPI write.

## Exact-source integration; ownership preserved

| Lot | Source PR / exact SHA | Files reused | Boundary |
|---|---|---|---|
| 1/5 | #198 `8f48b1b5a94960ce4ddcc1ca35bf206302543e94` | `tools/find_acme_demo_run.py`, `tests/test_find_acme_demo_run.py` | Synthetic-only locator; protected Core evidence-refs route absent on main; tenant/runtime ACL NOT_ATTESTED |
| 3/5 | #197 `571943714ef3d3a30bf2205a8d94aa918db01e6e` | `app/shared/acme_evidence_utc_preflight.py`, `tests/test_acme_evidence_utc_preflight.py` | Injectable UTC preflight only, not an authenticated Core/GLPI/Evidence join |
| 4/5 | #199 `e0fc68f7b2f947c75d4eed035d682a45c88a78a0` | `app/policy/simulate_fixture.py`, `tests/test_policy_simulate_fixture.py` | What-if SIMULATE, `execution_allowed=false`; no approval authority |
| 5/5 | #195 `f9617b09fcb1b01f6d6d3a21aad0e0ecb867ba72` | 14 README/docs paths | Architecture, ITIL story, benchmark, reuse and release-kit audit, not runtime proof |

All six code/test files and 14 docs are copied as **exact source Git blobs**; no divergent branch is merged. The Quality workflow from #199 is extended to execute the two new **offline** regression suites, in addition to Policy SIMULATE. It introduces no schedule, cron or deployment job. Individual source PR CI is not combined-SHA CI.

## Blockers and excluded work

- #185 is a divergent scenario source (741 ahead / 43 behind main); its exact ZIP lacks migration 011, OIDC/HITL verifier, AI telemetry and architecture docs. **Do not merge wholesale**.
- 2/5 Portal: no source-backed run-detail route on main. Require a minimal main-based Portal handoff with tenant/run-scoped GET and negative tests, not a copied `app/portal/main.py`.
- #190 INGEST and #192/#193/#194/#196 overlap Core/Portal/Worker/Compose; selective port requires dependency/migration/contract and outbox failure-injection review. Migration 011, OIDC and AI telemetry **not yet included** here.
- #188 preferred daily full quality + optional 15-minute read-only runtime smoke; #189 duplicate inactive. #146/#153 auto-deploy disabled; #187 new stack deferred pending resource/security/retention review.

## Exact combined-SHA qualification required

GitHub Quality `policy-and-static` must actually run `test_acme_evidence_utc_preflight.py`, `test_find_acme_demo_run.py`, `test_policy_simulate_fixture.py`; inspect job results and artifact members/hashes. A green source PR alone cannot qualify this integration. Do not infer installed files from a manifest or ZIP label.

- T0 isolated CI: **PENDING combined-SHA result**.
- T1 ephemeral Core/Portal/GLPI integration: **NOT_TESTED**.
- T2 synthetic ACME SAN→Payments end-to-end on combined SHA: **NOT_TESTED**.
- T3 Debian deployed read-only: **NOT_ATTESTED** (`applied.sha`, image digests, authenticated smoke).
- T4 sandbox install/upgrade/rollback and failure injection: **NOT_TESTED**.
- T5 LIVE: **NO_GO / NOT_AUTHORIZED**.

Next: exact-head CI; 2/5 Portal route handoff; protected Core evidence refs; selective OIDC/outbox/AI telemetry; single cumulative ZIP with migrations, source manifest, checksums, SBOM if available and isolated rollback. All handoffs in [#186](https://github.com/alimtalbi-ata/aiops/issues/186).
