# AIOps 2.0 — 5/5 release gate snapshot

**Recorded:** 2026-10-30 12:15 UTC. **Single scenario candidate:** [PR #185](https://github.com/alimtalbi-ata/aiops/pull/185) draft, head `5782d6fcece32cfd38ada0d50bfe68a8b74bd164`. **Overall: RELEASE_STABLE=NO_GO.**

## Exact selective integration

| Lot | Source HEAD | Files copied as exact Git blobs |
|---|---|---|
| 1/5 | `f50d3dac3182fd5d7c2bc5cb9ba8cf1bbba486ca` | `tools/find_acme_demo_run.py`, `tests/test_acme_core_authenticated_probe.py` |
| 2/5 | `ca6feab123d552c32ea707620a9176757b88b822` | `app/portal/main.py`, `tests/test_demo_v2.py` |
| 3/5 | `18ff72e312d5af5c2df239b646de18c16c4c534c` | `app/shared/acme_itsm_evidence_link.py`, `tests/test_acme_noc_glpi_join.py` |
| 4/5 | `901c5bb86922504ef447609e5a286c783cf8060b` | `app/shared/acme_policy_demo_result.py`, `tests/test_acme_policy_demo_result.py` |

One 5/5 commit, no `demo_v2.py` overwrite, no new release PR, no stable/main mutation. The #185 PR base is `feat/cron-stable-reconciled-20261028`, **not** `main`; its 72-file diff must not be merged wholesale.

## CI gates at this snapshot

- New SHA V2.8 isolated [41053319372](https://github.com/alimtalbi-ata/aiops/actions/runs/41053319372): **FAILED** in `static-and-unit`, 59 tests / 1 error, `test_v28_portal_ui.PortalPageContractTests.test_demo_live_trace_is_source_backed`. Legacy fixture expects `response["gates"]["decision"]`, whereas the scoped Core gate reader now returns `{"items":[...]}` or `{"status":"UNKNOWN"}`. Do not relax identity checks; ask 2/5 to update fixture and add regression tests.
- New SHA Quality [41053319020](https://github.com/alimtalbi-ata/aiops/actions/runs/41053319020): **IN_PROGRESS** at snapshot (five jobs SUCCESS, release-kit pending). Do not count pending as PASS.
- New SHA Historical [41053319033](https://github.com/alimtalbi-ata/aiops/actions/runs/41053319033) and Offline [41053318999](https://github.com/alimtalbi-ata/aiops/actions/runs/41053318999): SUCCESS.
- #193 [41024125286](https://github.com/alimtalbi-ata/aiops/actions/runs/41024125286): targeted rerun 6/6 SUCCESS after pip transport `IncompleteRead`; this qualifies only that PR head.
- Local older operator archive `02dd3aa`: selected regression suite **193/193 PASS** and AI harness **3/3 PASS**. **Not** tests of the new `5782d6f` commit.

## Deployment and demo proof boundary

- `deploy/aiops2-stable` is exactly `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3` (0 ahead / 0 behind).
- Stable `deploy/deploy-demo-studio-v2.sh` copies only `app/portal/demo_v2.py` and `tests/test_demo_v2.py`, then patches `app/portal/main.py` locally. The candidate `deploy/poll-approved-deploy.sh` accepts only stable and refuses unsupported transport; it is not a four-image release path.
- Local preview on the *older* archive can be launched with `python3 scripts/check_demo_portal_preview.py --port 17777` from its extracted directory, then viewed at `http://127.0.0.1:17777/demo-studio/business-story`. This is a synthetic local preview, not a deployed customer URL.
- Operator-reported synthetic scenario IDs (not rechecked by this 5/5 run): `SCN-GOLDEN-PAYMENT-P1`, `RUN-73AFC6FF9315376C`, `INC-GOLDEN-P1-1edd0de6f46546e294139bf68d73d65a`. GLPI ticket, observed Payments impact, authenticated Evidence and runtime approval remain UNKNOWN; `INGEST=PENDING` was reported on the older run.
- New SHA CI artifact checksum, exact packaging, `applied.sha`, deployed image digest, Core/GLPI/Evidence authenticated read, Debian smoke and exercised rollback: **NOT_ATTESTED**.

## Decision and operator handoff

**DEMO_LOCAL=GO only for the earlier tested `02dd3aa` archive; NEW_CANDIDATE_CI=FAILED/PENDING; RELEASE_STABLE=NO_GO.** Next: 2/5 fixes the test fixture without weakening fail-closed checks; 5/5 integrates a new exact SHA, reruns all CI, validates the cumulative kit and obtains separately authorized read-only Debian preflight and rollback evidence.

#188 is the preferred daily quality + 15-minute read-only smoke design; #189 is a duplicate unmerged two-hour full quality cron. #146/#153 auto-deploy stays disabled, #187 new observability stack deferred. No merge, deployment, runner installation, cron change, LIVE action or host access was performed.
