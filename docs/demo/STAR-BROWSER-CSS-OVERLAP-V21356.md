# V2.13.56 — Chromium STAR: geometric proof/redaction fence

## Business need and regression

At each ACME SAN P1 / Payments P2 STAR checkpoint, an anonymized screenshot must retain legible `run_id`, `correlation_id`, event reference and observed state. V2.13.55 rejected identical selectors and masks containing proof nodes, but an absolutely/fixed-positioned **sibling** mask could still black out a proof label. Such a PNG could be integrity-checked (SHA-256) despite being unsuitable as evidence. This version rejects that geometry before screenshot or manifest creation.

## Historical source and traceability

- Source archive: `AIOps-V21355-STAR-Chromium-Mask-Proof-Fence-Offline.zip`, archive SHA-256 `86f7c915fdaadb97cb1a169939fcec49f6d6b0088adbd24baba45aae00b14979`.
- Original path: `demo/star_snapshot_browser.py`, original file SHA-256 `b9046e3ce7368e7d4f94bb47be602a19f01f8f4cc99a93266b5cda02073228fb`, Git blob `8a7b89fa5b8e72039cd58716e05f97e89d8c97ee` (PR #36 at `e1476cde8d6ed2451cb02f2dfdc635802070ddf5`).
- Original test: `tests/test_star_browser_mask_proof_gate.py`, SHA-256 `11efac2eaf781bb42fe71a4dc30745d1fac179a9476297de497323710b7efc00`.
- Supporting historical archive: `AIOps-V21346-Historical-Replay-Recovery-Cumulative-Offline-20261023.zip`, archive SHA-256 `bc6f8e11018602d6ec752c3fdad5c0e149ca9cab186f4054c368816f8ede5bc3` (supporting modules only; not a claim that F20.13 originals were recovered).
- Reuse decision: modify the existing complete Chromium collector, **do not** create another browser or duplicate a partial F20.13 fragment. No runtime credentials, session state, unredacted screenshots or production data are imported.

## Architecture / interface / dependencies

`CapturePlan` -> `validate_plan` -> isolated Playwright Chromium -> exact DOM identity/state -> redaction validation -> PNG + SHA-256 manifest (unreviewed). The existing `capture(plan, output_dir, approved_read=False, fixture_html=None)` interface is unchanged. The redaction loop now rejects masks whose DOM ancestry **or visible bounding rectangle** intersects any required proof element. CSS-positioned siblings and descendants are covered. `capture()` remains dry-run by default and respects `AIOPS_STAR_NO_RUNTIME=1`. Only `demo/star_snapshot_browser.py` and its existing regression test are changed; no portal route, Compose, port, DB, n8n, GLPI, Grafana or Temporal code is touched.

Dependencies: Python standard library, existing `demo.star_snapshot_choreography`, `demo.star_capture_identity_guard`, `demo.star_browser_request_fence`, and Playwright Chromium **only for explicit capture**. Geometry check is deliberately conservative: a bounding-box overlap may reject a mask even when its CSS clipping would not hide text; false rejection is preferable to publishing illegible proof. It does not authenticate page origin or establish event timestamps, operator approval, HITL or business success.

## Qualification and conditions for reuse

- Test on synthetic local HTML only, with `AIOPS_STAR_NO_RUNTIME=1` and no operator opt-in.
- Regression: mask sibling positioned over run ID -> fail closed, no files; sibling over state -> fail closed, no files; disjoint positioned mask -> PNG and manifest created; original selector/ancestor checks remain.
- Negative control: both new overlapping-mask tests **failed against the unchanged V2.13.55 source** and passed after this correction.
- Existing browser suite: 18 snapshot + 7 hardening + 7 mask + 7 request-fence = **39 PASS** locally on the isolated archive-based checkout; CI must independently verify the committed PR SHA.
- Screenshot PNG and SHA-256 attest only captured bytes. `runtime_page_authenticated`, `business_outcome_verified`, `human_approval_authenticated` remain false. No runtime screenshots or Debian `:17777` E2E qualification are claimed.

## Rollback

Revert the single V2.13.56 commit on the PR branch only, then rerun the four offline Chromium test suites. Do not merge automatically, deploy to Debian, restart containers, add ports or modify production data. Restore only the previous Git blobs; no data migration is needed.
