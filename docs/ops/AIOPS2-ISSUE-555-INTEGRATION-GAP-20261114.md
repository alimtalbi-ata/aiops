# AIOPS2 — issue #555 versus PR #713: integration gap register

Date: 2026-11-14. Scope: GitHub source inspection only. This is not a host, browser, runtime or CI attestation.

## Executive finding

GitHub issue [#555](https://github.com/alimtalbi-ata/aiops/issues/555) is an **integration coordination issue**, not PR #555. It calls for selective consolidation of five parallel Portal UI efforts, exact-head CI, actor/tenant security, and independent review. The SAN→Payments customer-demo PR [#713](https://github.com/alimtalbi-ata/aiops/pull/713) is a separate integration candidate. Its current branch does **not** contain the original source files enumerated below. Missing files are not proof that equivalent behavior is absent elsewhere; functional equivalence remains **NOT_VERIFIED**.

## Source-file gap matrix (GitHub inspection)

| Source PR | Concern | Original files absent from PR #713 branch | Qualification required |
| --- | --- | --- | --- |
| [#538](https://github.com/alimtalbi-ata/aiops/pull/538) | Framework 404/405 security headers; navigation supersession | `tests/test_portal_error_response_security_20261110.py`; `tests/test_portal_method_error_security_20261110.py`; `tests/test_portal_navigation_supersession.mjs` | Confirm equivalent FastAPI security-header and stale-navigation tests against the **current** Portal |
| [#541](https://github.com/alimtalbi-ata/aiops/pull/541) | Contradictory evidence identifiers fail closed | `app/portal/components/evidence_filter.mjs`; `app/portal/components/evidence_filter.test.mjs` | Identify current evidence filtering path, actor/tenant authorization, conflicting-ID negative test |
| [#550](https://github.com/alimtalbi-ata/aiops/pull/550) | Genuine timeout versus transport-error spoofing | `app/portal/components/operational_state.mjs`; `app/portal/components/operational_state.test.mjs` | Test cancellation, late results, timeout sentinel and transport failures without leaking secrets |
| [#551](https://github.com/alimtalbi-ata/aiops/pull/551) | Accessible Prometheus history empty state | `scripts/fs/fs1097_patch.py`; `scripts/fs/tests/test_fs1113_history_empty_accessibility.py` | Locate current history UI and verify empty-state text, keyboard/ARIA, screen reader semantics |

These absences were checked directly at `integration/aiops2-convergence-20261114` on 2026-11-14. The source PRs were open/draft/unmerged when inspected. Source PR bases are not all `main`; do not assume standalone cherry-picks are safe.

## Current candidate and decision

PR #713 HEAD at inspection: `cd0429a0a93212ccb0add6808793fbbebddb61d0`. It contains a synthetic SAN→Payments cockpit, Grafana preview, offline evidence and read-only qualification gates. Its HTTP write-method regression is specific to customer-demo routes; it is **not** equivalent proof for all historical Portal navigation/FS1113 behavior. No authenticated real Grafana/GLPI/Temporal runtime is attested. Exact-head CI for this revision is **NOT_VERIFIED**.

**Integration verdict: HOLD / NO-GO LIVE.** Do not merge, deploy, rebase or cherry-pick based solely on this matrix. The #535 credential and #557 Debian Docker-storage blockers remain independent.

## Controlled next steps

1. Inventory the actual Portal entrypoints and identify behavioral replacements for each absent source module.
2. For each #555 concern, record **equivalent / missing / incompatible / not applicable**, with a code path, test and expected denial behavior.
3. Assemble only reviewed deltas against an approved integration base; avoid replacing unrelated Portal components or five Debian stacks.
4. Run combined regression on the exact final SHA: 404/405 headers, stale navigation, evidence conflicts, timeout spoofing, Prometheus empty-state accessibility, 401/403 and cross-tenant denial, plus the SAN→Payments 8–12 minute synthetic operator demo.
5. Attach CI and independent review evidence; keep LIVE and host qualification **UNKNOWN/BLOCKED** until independently attested.

No customer-demo receipt should claim #555 integration completed merely because #713 demo smoke passes.
