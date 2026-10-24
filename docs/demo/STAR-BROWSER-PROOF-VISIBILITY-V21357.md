# V2.13.57 — STAR Chromium: visually invisible proof rejection

## Business need / observed defect
ACME SAN P1 -> Payments P2 requires screenshots with legible run, correlation, event and state identifiers at the exact checkpoint. Playwright `locator.is_visible()` can return true for text styled `opacity:0` or `color:transparent`: the DOM identity is correct but the resulting PNG lacks visible proof. This was reproduced on the unchanged V2.13.56 collector using isolated synthetic HTML. A SHA-256 checksum alone cannot detect semantic absence of proof.

## Historical provenance and deduplication
- Original complete module: `demo/star_snapshot_browser.py` from `AIOps-V21356-STAR-Chromium-CSS-Overlap-Fence-Offline.zip`.
- Original archive SHA-256: `f97a52893e9acd203c2052dfbb0f3617473191edb4ca7e13f33e22f5c7bcbf14`.
- Original module SHA-256: `a74bb5fd3e12fef32db339f547af216286a7335e8e69918f9750365584eb72f1`; original Git blob `300997d4d8c42d8474389aa4684e671558071a5a` at PR #36.
- Updated module Git blob: `523ae31e00a1e83ad7bbdad6d072418f66006273`.
- Original supporting test: `tests/test_star_browser_mask_proof_gate.py`, SHA-256 `2a4fe5b884fd02cc60267fa937ae20961daa4e4784decd56c9db2e7b6da02529`.
- New regression: `tests/test_star_browser_proof_visibility.py`, entirely synthetic.
- Reuse decision: patch the existing complete Chromium collector; no second browser, no guessed F20.13 implementation, no historical fragment promoted to a complete module. Original F20.13 Playwright sources remain unverified/unrecovered.

## Architecture and interfaces
Existing flow: `CapturePlan -> validate_plan -> Playwright Chromium -> exact DOM identity/state -> redaction geometry -> PNG + SHA-256 manifest`. The existing `capture(plan, output_dir, approved_read=False, fixture_html=None)` API remains unchanged. After the Playwright visibility check and before accepting the DOM text, Chromium now rejects proof when the computed text color has near-zero alpha, the font size is zero, or any ancestor has near-zero CSS opacity. This is a fail-closed visual eligibility check, **not** screenshot OCR, pixel proof, timestamp attestation or business validation.

Dependencies: existing `demo.star_snapshot_choreography`, `demo.star_capture_identity_guard`, `demo.star_browser_request_fence`, Python standard library, Playwright Chromium for explicit capture. The browser remains dry-run by default. `AIOPS_STAR_NO_RUNTIME=1` prevents runtime navigation during CI. No credentials, sessions or real screenshots are committed.

## Qualification and limitations
- Negative controls on V2.13.56: transparent run, transparent state and opacity-zero ancestor were accepted as screenshots; new tests exposed the defect. Zero-font-size already failed via the prior visibility check.
- Local candidate: five new tests and seven existing mask regression tests passed with isolated Chromium, synthetic HTML and minimal dependency stubs; the full repository CI remains the authoritative integration check.
- The new CI test is included in `.github/workflows/star-browser-readonly-offline.yml`. Verify its result on the final PR head before declaring the release qualified.
- Limits: CSS clipping, blending, filters and occlusion by non-mask overlays are not comprehensively verified; PNG bytes remain `CAPTURED_UNREVIEWED_NOT_BUSINESS_PROOF`. The portal Debian `:17777`, GLPI `:8080`, n8n `:5678` and Grafana `:3000` were not contacted.
- Conditions for reuse: synthetic/isolated Chromium test PASS, dedicated CI PASS, global CI review, code review and provenance check; operator approval is separately required for any future runtime evidence collection.

## Rollback
On the PR feature branch only, revert the V2.13.57 changes to `demo/star_snapshot_browser.py`, its new regression test, workflow and this document. Re-run the isolated Chromium suites. No migration, deployment, port, service restart, database, GLPI/n8n/Grafana or LIVE remediation is involved. Never merge automatically into `main`.
