# AIOps V2.13.67 — F20.13 login-screen lesson integrated into STAR Chromium

Date: 2026-10-24. Scope: **offline synthetic browser qualification only**. No Debian, production containers, credentials, application writes, network ports or LIVE actions.

## Historical provenance and reuse decision

The private metadata-only F20.13 ZIP inventory records the complete candidate
`AIOps-UCP-F20.13-DEMO-MULTISTACK-KIT-v0.3/scripts/capture-multistack.py`,
from `AIOps-UCP-F20.13-DEMO-MULTISTACK-KIT-v0.3.zip`,
with source SHA-256 `bc8fb46e81d37cb90f64d53feaa7e14171aa65e0137a0143650ba04d12e623ee`
and archive SHA-256 `cc2fdc0f1d7b2b3e82937925030d7dbb978fe341f4ed2d74030e59462a7190f1`.
Inventory reported syntax `AST_PASS_NOT_COMPLETENESS`. **These pins are copied from the prior private inventory, not independently rehashed this cycle.** No raw source or historical screenshots are republished. This is a behavioral safety lesson, **not an import of the historical collector**.

Prior F20.13 capture reports described GLPI :8080, n8n :5678 and Grafana :3000 login views despite a PASS tally. This motivates rejecting a login surface even when run/correlation/event/state DOM fields appear to match. A historic PASS is not an authenticated business screenshot.

## Business objective, design and interfaces

Goal: preserve the exact STAR checkpoint application view; never label a login page as an incident, execution or dashboard capture. Existing `demo/star_snapshot_browser.py` remains the single capture implementation, with explicit opt-in, read-only network fence, exact URL/identity/state verification, mandatory redaction and synthetic provenance.

After navigation or local `page.set_content()` and before proof inspection, `capture()` rejects a visible password input, a visible form whose action contains `login`, or a visible form whose action contains `signin` (case-insensitive). No password, username, form content or URL is read into evidence. A hidden login widget does not automatically reject a legitimate visible event view. A rejection happens before PNG/manifest output.

This is a **negative heuristic**, not a login authentication oracle: SSO-only pages with no matching form can still require separate exact-page selectors, authenticated session validation and operator review. The capture result remains `CAPTURED_UNREVIEWED` with `runtime_page_authenticated=false` and `business_outcome_verified=false`. No code path elevates the result to authenticated.

## Dependencies and qualification

Only the existing Playwright Chromium dependency is used. Synthetic regression tests in `tests/test_star_snapshot_browser.py` exercise a visible password form with spoofed proof DOM, a passwordless signin form, and a hidden login widget. Existing request-fence, redaction and proof-visibility tests remain required.

Run in an isolated checkout with Chromium:
`AIOPS_STAR_NO_RUNTIME=1 python -m unittest discover -s tests -p 'test_star_snapshot_browser.py' -v`.
GitHub workflow `STAR Chromium read-only fixture qualification` executes this suite. Passing isolated tests does **not** qualify production portal :17777 or any real application screen.

## V2.13.68 — Screenshot-boundary consistency (isolated regression)

The initial login-surface check alone could not detect a late single-page
application transition **after** proof DOM inspection but **during** Chromium
`page.screenshot()`. The collector now repeats the visible login-surface
check and exact run/correlation/event/state DOM validation immediately after
the screenshot returns and **before any PNG or manifest is written**. Any
disagreement rejects the entire capture, preserving the fail-closed evidence
contract. The existing request fence, mandatory redaction and explicit
unreviewed provenance are unchanged.

`tests/test_star_snapshot_browser.py::BrowserContractTests.test_dom_mutation_during_screenshot_fails_closed`
uses a real isolated Chromium fixture and deterministically injects three
mutations at the screenshot boundary: a visible login form, a changed run ID,
and a changed business state. All must reject without creating evidence files.
No historical browser sessions or production data are used. This test addresses
a safety lesson from the F20.13 source catalog; it **does not** establish
completeness or authenticity of any historical capture.

This is a before/after DOM consistency gate, **not a transactional browser
snapshot**: transient changes that appear and disappear between checks may
remain undetectable. No authentication, human approval or real incident
outcome is asserted. To roll back, revert the capture-code commit and its
regression-test commit on the PR branch only; no runtime rollback is needed.

## Migration, limitations and rollback

The historical source stays in private quarantine. Compare its full code to the current implementation by exact SHA and review before any reuse; do not copy unreviewed selectors, sessions, passwords or endpoints. Remaining work: independent read-only E2E attestation of nine STAR checkpoints, identity 02→03, event-time alignment, screenshots and human provenance review.

Rollback: revert the two code/test commits and this document on the draft PR branch only. No runtime rollback, database writes or container operations are involved.
