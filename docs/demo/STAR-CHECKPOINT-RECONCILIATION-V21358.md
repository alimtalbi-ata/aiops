# STAR checkpoint reconciliation — candidate V2.13.58

## Purpose
Pure offline guard linking independently supplied canonical `run_id`, `correlation_id` and checkpoint event references to screenshot metadata. A screenshot is never proof of operational success.

## Architecture
Input A: independently sourced canonical event map. Input B: capture manifests already checked for file integrity by `star_browser_manifest_gate.py`. This reconciliation is a second identity/coverage gate, **not a replacement for PNG/hash verification or authenticated runtime evidence**.

## Interface
`reconcile_checkpoints(expected, captures)` accepts a canonical map with `run_id`, `correlation_id`, `events` and a list of checkpoint metadata. Requires complete one-to-one checkpoint coverage, matching IDs, SHA-256 syntax, explicit unreviewed provenance and explicit false attestation flags. Raises `ValueError` on contradictions; never silently repairs identity.

## Security
No HTTP, browser, tokens, Docker, database, ticket, Policy or LIVE operations. `CAPTURES_UNREVIEWED` is the only success label. The hash is checked for syntax only; the upstream manifest gate must validate bytes and source provenance. Synthetic fixtures are never called authentic screenshots.

## Qualification
Run `python -m unittest tests.test_star_checkpoint_reconciliation -v` from repository root. Chromium and deployed portal E2E remain separate, not established by these unit tests.

## Rollback
Revert commits introducing `demo/star_checkpoint_reconciliation.py`, its test and this document on the draft branch. Do not deploy or merge automatically.

## Continuity
F20.13 originals and runtime evidence are not restored by this module. Continue archive provenance inventory and isolated Chromium validation before integrating into portal :17777.
