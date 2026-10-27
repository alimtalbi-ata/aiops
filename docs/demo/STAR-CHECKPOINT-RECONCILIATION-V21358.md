# STAR checkpoint reconciliation — candidate V2.13.58

## Purpose
Pure offline guard linking independently supplied canonical `run_id`, `correlation_id` and checkpoint event references to screenshot metadata. A screenshot is never proof of operational success.

## Architecture
Input A: independently sourced canonical event map. Input B: capture manifests checked for PNG byte integrity by `star_browser_manifest_gate.py`. Call `verify_browser_manifests(root, expected, filenames, require_complete=True)` to apply the manifest gate **and** `reconcile_checkpoints` in one read/validation pass. Default `require_complete=False` preserves existing partial, explicitly missing storyboard behavior. This reconciliation is a second identity/coverage gate, **not a replacement for PNG/hash verification or authenticated runtime evidence**.

## Interface
`reconcile_checkpoints(expected, captures)` accepts a canonical map with `run_id`, `correlation_id`, `events` and a list of checkpoint metadata. Requires complete one-to-one checkpoint coverage, matching IDs, SHA-256 syntax, explicit `CAPTURED_UNREVIEWED_NOT_BUSINESS_PROOF` qualification and explicit false attestation flags. The strict mode requires all nine canonical STAR cues and nine distinct manifest filenames. Raises `ValueError` on contradictions; never silently repairs identity.

## Deterministic capture-set binding (V2.13.59)
After the nine PNGs have been verified byte-for-byte and their manifests have passed independent identity, chronology, provenance and coverage checks, `verify_browser_manifests(..., require_complete=True)` returns `capture_set_sha256`. It is SHA-256 of canonical sorted-key compact UTF-8 JSON containing schema `star-capture-set-binding/v1`, canonical run and correlation IDs, independent event refs in STAR order, and nine sanitized entries (view, state, capture timestamp, PNG digest, byte count). Manifest input order is irrelevant. A changed timestamp, image or canonical event reference changes the digest. Partial mode intentionally omits this field. The digest is a **replay consistency identifier only**; it is not a digital signature, not proof of authenticated GLPI/n8n/Grafana access, and not a LIVE remediation or HITL approval.

## Historical provenance and recovery boundary
The full original F20.13 Playwright browser sources remain unverified and are not silently substituted with the newer Chromium implementation. Existing `demo/star_snapshot_browser.py`, `demo/star_browser_manifest_gate.py`, and `demo/star_checkpoint_reconciliation.py` are reused. Do not import unreviewed archives into the portal or claim the manifest digest authenticates historical sources.

## Security
No HTTP, browser, tokens, Docker, database, ticket, Policy or LIVE operations. `CAPTURES_UNREVIEWED` is the only success label. The hash is checked for syntax only; the upstream manifest gate must validate bytes and source provenance. Synthetic fixtures are never called authentic screenshots.

## Qualification
Run `python -m unittest discover -s tests -p 'test_star_checkpoint_reconciliation.py' -v` and `python -m unittest discover -s tests -p 'test_star_browser_manifest_gate.py' -v` from repository root. The offline GitHub Actions manifest-bridge workflow runs both suites. Chromium and deployed portal E2E remain separate, not established by these unit tests.

## Rollback
Revert commits introducing `demo/star_checkpoint_reconciliation.py`, its test and this document on the draft branch. Do not deploy or merge automatically.

## Continuity
F20.13 originals and runtime evidence are not restored by this module. Continue archive provenance inventory and isolated Chromium validation before integrating into portal :17777.
