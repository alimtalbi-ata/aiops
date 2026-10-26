# STAR screenshot manifest — stricter offline ingestion

**Status:** source-level hardening; isolated synthetic tests only. This is not runtime authentication or a production release.

## Defect and fix

The historical/cumulative screenshot collector already checked PNG structure, SHA-256, run identity and nine STAR cues. Its CLI reader used ordinary `json.loads`, so a JSON object containing duplicate keys could be interpreted with last-key-wins semantics. Its path handling also followed a symlink for the manifest and read the declared size before opening the file.

`demo/star_capture_evidence.py` now reads a bounded byte buffer from a regular file, refuses a final symlink (and uses `O_NOFOLLOW` where supported), verifies UTF-8, and rejects duplicate JSON keys at every nesting level. It validates that the capture map and each capture record are objects before field access, returning controlled `ValueError` failures rather than leaking incidental `AttributeError`/JSON parsing details. The screenshot byte hash is still computed on the actual PNG file, not trusted from its manifest. The shared PNG verifier now opens once, refuses final-component symlinks, requires a regular file from `fstat`, and compares descriptor metadata before/after parsing so a concurrent append, truncation or modification fails closed. Validation and digesting use that same open descriptor rather than a pre-open path-size check.

## Interface and dependencies

- Input: a local JSON manifest and a local evidence root; no HTTP, browser launch, Docker, credentials, application API or database.
- Output: sanitized integrity summary, with `runtime_authenticated=false`, `business_validated=false`, `human_approval_authenticated=false`, and `live_action_authorized=false`.
- Dependencies: Python standard library, `demo.star_snapshot_choreography`, and `demo.star_png_integrity`.
- Candidate package: the source, direct dependencies, workflow, documentation and regression tests are explicitly admitted to the cumulative source subset and checked byte-for-byte.

## Qualification

Regression tests cover duplicate keys at root and nested record level, symlink refusal, bounded size, invalid UTF-8 and non-object capture records. The existing synthetic PNG suite remains byte-level structure/integrity only. A passing digest does not attest the image source, authenticated session, expected application screen, timestamp origin, or business event.

## Safety and rollback

The module remains an offline verifier; the change performs no live capture and no external write. Rollback is source-only on the PR branch: revert this commit. Do not run historical F20.13 scripts against Debian or legacy application ports. Production remains blocked until authenticated runtime E2E, nine exact application checkpoints, independent event provenance, backup/restore and explicit release approval are qualified.
