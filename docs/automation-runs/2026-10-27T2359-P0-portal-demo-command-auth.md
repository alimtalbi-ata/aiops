# Automation development log — 2026-10-27 23:59 Europe/Paris — P0 Portal

- **Start HEAD (`main`):** `0603e86a26978873c3b6196098674932d3378499` (confirmed via GitHub fetch_commit).
- **Dedicated branch:** `fix/portal-demo-command-rbac-20261027-2357`; **draft PR:** [#57](https://github.com/alimtalbi-ata/aiops/pull/57).
- **Scope:** prevent anonymous Golden DEMO writes; no LIVE commands, no Debian access, no merge.
- **Read before change:** main portal/Compose/quality, README, continuity, architecture, decision log, reuse catalog; PR #36 changed-file inventory and `noc_runtime.py` security pattern; PR #37/#39/#41/#43 metadata; PR #51 operator RBAC contract. No mass merge.
- **Changed files:** `app/portal/portal_command_auth.py` (new guard), `app/portal/main.py` (operator header and one-shot UI credential), `compose.yml` (optional operator secret injection), `tests/test_portal_demo_command_auth.py` (10 HTTP contract cases), `.github/workflows/quality.yml` (reuse existing gate), `docs/portal/GOLDEN-DEMO-COMMAND-RBAC.md`, this journal.
- **Confirmed commits:** `c83f3c0`, `8d61f1c`, `7d9382a`, `fa88e9f`, `93989a1`, `5c1a49d`.
- **Tests authored:** 10 in-process FastAPI HTTP cases (unconfigured/weak/colliding token, absent/wrong/viewer/basic token, positive DEMO-only path, health, UI non-disclosure). These replace the Core client with a test double; **not** real Core integration.
- **Executed tests at journal creation:** NOT_TESTED. GitHub Actions PR trigger requested by PR creation; run result pending. Local clone was blocked by unavailable DNS (`github.com`); no false PASS.
- **Risks:** existing public bootstrap/Copilot/home routes remain unprotected; PR #51 changes the same `main.py` and Compose and may need a targeted rebase before merge. Operator token must be injected from secrets; absent token disables the DEMO command intentionally. No browser/runtime capture attested.
- **Next micro-lot:** inspect GitHub quality job, correct failures, rebase against PR #51 as needed, then enforce RBAC on remaining legacy reads and Copilot; validate real ephemeral Core/Temporal integration separately.

## CI results confirmed after first run

- First run [40598872077](https://github.com/alimtalbi-ata/aiops/actions/runs/40598872077): **FAILURE** in the new HTTP tests. Root cause: importing `portal.main` requires an internal token at import time via `shared.http`; the CI job correctly had no production secret.
- Fix commit `0c7978f24e679e3e5e3606b602df79143e889ba3`: inject an isolated, synthetic unit-test internal token during module import, with no real backend calls.
- Re-run [40598932248](https://github.com/alimtalbi-ata/aiops/actions/runs/40598932248) for fix commit: **SUCCESS** (confirmed GitHub Actions conclusion). New DEMO authorization tests, pre-existing policy/read-model/NOC tests, static audit and Docker Compose config validation all passed. This is **in-process and static CI**, not a live service integration.
- The journal-only follow-up commit will trigger a further PR check; its result must be verified separately before merge.
