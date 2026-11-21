# ACME — Inventory of existing screenshot pipelines (source review, 2026-11-17)

**Status: SOURCE_REVIEW_ONLY; runtime, browser, exact-SHA CI and seven ACME scenes NOT_TESTED.** This document is a decision aid, not a runtime acceptance receipt. PR #806 was closed without merge because it duplicated existing code.

## Actual source files and interfaces

| Source PR / branch | File / API | Actual contract | Reuse / limitation |
|---|---|---|---|
| [#404](https://github.com/alimtalbi-ata/aiops/pull/404), present on #805 ancestry | `deploy/debian-portal-playwright-snapshot.py`: `run(args)`, `capture(page, folder, name, receipt)`, `verify_base_url(raw)`, `observed_provenance()` | Read-only anonymous Chromium; exact local checkout SHA + Docker image ID; screenshots via 0600 temp + atomic replace + SHA256; same-origin GET-only fence; console/request error counters | **Existing runtime capture engine**. Targets known Portal routes on port **7777** and uses Debian host assertion; must not be repurposed or invoked against LIVE without authorization |
| [#407](https://github.com/alimtalbi-ata/aiops/pull/407) | Existing Debian poller integration | Host Chromium qualification via existing poller; private redacted SHA-bound metadata | **Do not add a new schedule or host job**. Evidence from host must be independently verified |
| [#735](https://github.com/alimtalbi-ata/aiops/pull/735), `test/noc-browser-a11y-20261116` | `tests/test_aiops2_noc_browser_a11y.py` | `pytest-playwright` `page` fixture; `render_decision_cards(projection())`; 320/768/1440 viewports; external request abort; `NOC_SCREENSHOT_DIR` optional PNG + SHA256 sidecar | **Offline isolated renderer**, not real Portal route or Debian capture |
| [#752](https://github.com/alimtalbi-ata/aiops/pull/752), `ux/noc-browser-evidence-manifest-20261116` | `tests/test_noc_capture_manifest_contract.py`: `validate_manifest(records, source_sha)` | Exactly **three records**, 320/768/1440, `browser_executed`, `screenshot_sha256`, `screenshot_path`, `DENY_LIVE`, `UNKNOWN`, `external_requests=0` | Metadata contract only, **does not read PNG bytes** |
| [#757](https://github.com/alimtalbi-ata/aiops/pull/757), `ux/noc-capture-integrity-gate-20261116` | `scripts/noc_capture_integrity_gate.py`: `qualify(manifest, root, expected_sha)` | `manifest.captures` with **exactly three viewports**; SHA256 actual bytes; PNG header/IHDR dimensions; policy `DENY_LIVE`, HITL `REQUIRED`; rejects missing/unsafe paths | **Offline byte integrity**, not browser authenticity or full PNG decoding |
| [#761](https://github.com/alimtalbi-ata/aiops/pull/761), `ux/noc-capture-gate-negative-tests-20261116` | `tests/test_noc_capture_integrity_gate_negative.py` | Nine negative tests plus a synthetic header-only positive fixture | Fixture can pass byte gate without being a decodable PNG: **do not call it a browser proof** |
| [#780](https://github.com/alimtalbi-ata/aiops/pull/780) | Keyboard / browser evidence checks | Offline accessibility, focus, responsive and manifest assertions | Source dependencies/ancestry need review before selective import |

## Critical mismatches — do not silently glue them together

1. **Different manifests**: #752 expects a list of records with `viewport`, `screenshot_path`, `browser_executed`; #757 expects a dict with `captures`, `viewport_width`, `file` and four boolean assertions. The Debian runner produces a **third** format (`screenshots: [{name, bytes, sha256, viewport}]`, plus `stable_checkout_sha` and `portal_image_id`). None is a drop-in replacement for another.
2. **Different evidence target**: the offline NOC gate checks **three widths of one synthetic renderer**, not **seven distinct ACME story scenes**. Seven scenes cannot be claimed from three responsive PNGs.
3. **Different Portal origin**: Debian runner uses canonical loopback `:7777`, while the new proposed scene YAML assumed `:17777`. Neither proves a deployed ACME route. Do not assert route availability without a source-backed route map and sandbox browser run.
4. **Source SHA vs deployed SHA**: a user-provided `DEPLOYED_SHA` is not provenance. The Debian runner probes local checkout SHA and Docker image ID; these must be matched to observed deployment, not copied from branch HEAD.
5. **Safety and privacy**: existing host capture uses atomic private PNGs and GET-only same-origin. The closed #806 draft wrote PNGs directly to a repository-relative folder and did not implement the host network fence; **do not resurrect that runner**.
6. **Acceptance gap**: `GO_SIMULATION_ONLY` from `assess()` checks receipt contract, not the Portal, the browser, 7 scenes, or Core→Twin joins. These remain separate gates.

## Decision / next incremental patch

**Reuse first**: retain the Debian snapshot runner unchanged for host qualifications; reuse the offline NOC browser and integrity gates selectively after source/branch reconciliation. No new Playwright engine, no new poller and no bulk cherry-pick.

**Minimal future ACME adapter (proposal, not implemented)**: a separate read-only scene contract that maps **confirmed Portal routes** and selectors to the existing private `capture()` mechanism, with per-scene status `NOT_IMPLEMENTED` until proven. Keep browser network fence, private file mode, atomic writes, provenance checks and privacy review. Adapt metadata explicitly rather than treating three incompatible manifest schemas as equivalent. Require seven scene-specific PNGs and a separate verified E2E receipt before an evidence-pack PASS.

## Release gates

- Source review of actual Portal routes and tenant ACL before any browser test.
- Exact-SHA CI for any selected patch, including failure-path tests.
- Explicit authorization before a disposable sandbox browser run; **no Debian host mutation, no LIVE, no GLPI/Temporal/DB changes**.
- Manual privacy review of screenshots; publish only redacted, SHA-bound metadata until approved.
- Report **NOT_TESTED** when no actual Chromium execution and screenshot bytes were observed.

Tracked in [#804](https://github.com/alimtalbi-ata/aiops/issues/804).
