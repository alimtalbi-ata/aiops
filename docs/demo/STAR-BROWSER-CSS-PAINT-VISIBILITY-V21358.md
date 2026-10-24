# STAR Chromium — V2.13.58 CSS paint visibility fence

Date: 2026-10-24. Scope: **offline, isolated, synthetic-only**. No deployment.

## Provenance and recovery
- Existing complete module: `demo/star_snapshot_browser.py` on PR #36, original Git blob SHA **523ae31e00a1e83ad7bbdad6d072418f66006273** (V2.13.57). The code was modified in place; no historical module was duplicated.
- Related existing modules: `demo/star_snapshot_choreography.py`, `demo/star_capture_identity_guard.py`, `demo/star_browser_request_fence.py`; retained without modification.
- Historical lineage: F20.13 Chromium/Playwright checkpoint capture. **Original F20.13 full archive not available in this cycle**; no claim that a recovered fragment is a complete historical source.
- Business need: prevent a syntactically matching DOM element from being recorded as visible evidence when CSS makes the proof disappear in the PNG.

## Architecture and interfaces
`capture(CapturePlan, output_dir, approved_read, fixture_html)` calls `required_text` for independently supplied `run_id`, `correlation_id`, `event_ref`, and observed state. The Chromium computed-style inspection now rejects paint-suppressed proof on the element/ancestor chain: CSS filters, clip-path, mask-image, and transparent WebKit text fill. This complements existing opacity, transparent color, masking-overlap, identity, request-fence and SHA-256 checks.

This is a conservative **fail-closed** gate: even benign filter/clip/mask styling on a proof ancestor is rejected until explicitly reviewed. It does not claim OCR-level legibility, genuine application provenance, business success or human approval. It never authorizes LIVE operations.

## Qualification and dependencies
- Baseline V2.13.57 reproduced **4 false accepts** with synthetic HTML (CSS filter opacity zero, clip-path, transparent WebKit text fill, CSS mask-image).
- Updated module: **5/5 new tests PASS**, **5/5 prior visibility tests PASS**, **7/7 mask regression tests PASS**, local Chromium 144, Playwright, no HTTP; isolated harness used minimal local dependency stubs for non-target modules.
- GitHub Actions runs tests against actual repository dependencies and sets `AIOPS_STAR_NO_RUNTIME=1`; CI status must be checked separately.
- Input provenance remains `ISOLATED_TEST_FIXTURE` or `OPERATOR_BROWSER_UNREVIEWED`; output remains `CAPTURED_UNREVIEWED_NOT_BUSINESS_PROOF`.
- No genuine n8n :5678, Grafana :3000, GLPI :8080 or portal :17777 access was performed.

## Reuse / rollback
Keep the check only when exact DOM proof selectors are available and CSS effects are understood; reject and investigate unexpected legitimate styling instead of weakening the gate. Roll back this change by reverting its single Git commit on the PR branch after tests; no DB migration, port change, deployment or container operation is involved.
