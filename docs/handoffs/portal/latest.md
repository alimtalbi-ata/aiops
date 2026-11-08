# Portal handoff — 2026-11-08 18:51 UTC

- Role/issue: Portal / #461; branch `agent/portal/461-live-hold-selection`; source commits `c1b767e7402e623918fa58097b26db387f02c5aa` (code), `53267535583ebbb7df505c270b8cff08006b575c` (tests).
- Paths: `app/portal/live_hold_selection.py`, `tests/test_portal_live_hold_selection.py`. Mixed-owner receipts now exclude explicit Policy/HITL components even if `owner=portal`; browser HOLD remains actionable. Two new synthetic regressions.
- Interface: read-only `first_portal_hold(receipt, now_utc)`; no backend calls, approvals, resolutions or GLPI writes. Dependencies: Debian `latest-usecase.json` schema and Policy/Portal owner labels.
- Tests: 2 tests added; **NOT EXECUTED**. Run `python -m unittest tests.test_portal_live_hold_selection` in isolated worktree. CI: NOT_VERIFIED; Chromium FS1113: NOT_VERIFIED.
- Debian: `ops/debian-runtime-reports:ops/debian-reports/SRV-DEB-05/latest.json` collected `2026-11-08T18:50:01.970294Z`, fresh at consultation ~18:51 UTC (<3 min); portal image `aiops2-portal:fs1073-csp-candidate` running. No source SHA/digest attested. `latest-usecase.json` fetch unavailable: UNVERIFIED, not FAIL. Re-check freshness before any later use.
- CODE: committed; CI: NOT_VERIFIED; DEBIAN: report only; E2E: NOT_VERIFIED. Gate: NO_GO.
- Risks: Policy component classification requires explicit metadata; unknown labels fail closed only when no Portal-owned actionable HOLD. Rollback: revert additive source/test commits on isolated branch; production unchanged.
- Next owner: Integration confirm producer/receipt schema and evidence; Portal run unit tests and isolated Chromium matrix 1h/6h/24h for availability/scrape_duration, rapid period changes, refresh, mobile, before any promotion.
