# STAR checkpoint reconciliation — candidate V2.13.58

## Purpose
Pure offline guard linking independently supplied canonical `run_id`, `correlation_id` and checkpoint event references to screenshot metadata. A screenshot is never proof of operational success.

## Architecture
Input A: independently sourced canonical event map. Input B: capture manifests checked for PNG byte integrity by `star_browser_manifest_gate.py`. Call `verify_browser_manifests(root, expected, filenames, require_complete=True)` to apply the manifest gate **and** `reconcile_checkpoints` in one read/validation pass. Default `require_complete=False` preserves existing partial, explicitly missing storyboard behavior. This reconciliation is a second identity/coverage gate, **not a replacement for PNG/hash verification or authenticated runtime evidence**.

## Interface
`reconcile_checkpoints(expected, captures)` accepts a canonical map with `run_id`, `correlation_id`, `events` and a list of checkpoint metadata. Requires complete one-to-one checkpoint coverage, matching IDs, SHA-256 syntax, explicit `CAPTURED_UNREVIEWED_NOT_BUSINESS_PROOF` qualification and explicit false attestation flags. The strict mode requires all nine canonical STAR cues and nine distinct manifest filenames. Raises `ValueError` on contradictions; never silently repairs identity.

## Security
No HTTP, browser, tokens, Docker, database, ticket, Policy or LIVE operations. `CAPTURES_UNREVIEWED` is the only success label. The hash is checked for syntax only; the upstream manifest gate must validate bytes and source provenance. Synthetic fixtures are never called authentic screenshots.

## Qualification
Run `python -m unittest discover -s tests -p 'test_star_checkpoint_reconciliation.py' -v` and `python -m unittest discover -s tests -p 'test_star_browser_manifest_gate.py' -v` from repository root. The offline GitHub Actions manifest-bridge workflow runs both suites. Chromium and deployed portal E2E remain separate, not established by these unit tests.

## Rollback
Revert commits introducing `demo/star_checkpoint_reconciliation.py`, its test and this document on the draft branch. Do not deploy or merge automatically.

## Continuity
F20.13 originals and runtime evidence are not restored by this module. Continue archive provenance inventory and isolated Chromium validation before integrating into portal :17777.
