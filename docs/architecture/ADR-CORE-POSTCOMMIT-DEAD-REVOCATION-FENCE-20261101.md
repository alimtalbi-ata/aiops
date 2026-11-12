# Core P0 — post-commit DEAD revocation fence (2026-11-01)

Status: synthetic disposable regression; source-only, **not** a Debian or human GLPI attestation.

## Boundary

The canonical `core.main.app` HTTP `POST /api/tenants/{tenant_id}/hitl/reject-delivery/{event_id}/dead` commits a terminal REJECT after the eighth expired lease, with one immutable 014 receipt. A subsequent request bearing the *same* lease token is **not** a standing authorization. Service credential revocation must return 401; removal of `hitl:reject:terminal` must return 403; missing independent Core run ownership proof must return 200 `UNKNOWN`. Late ACK remains 200 `UNKNOWN`. The persisted DEAD/014 audit must survive all denials. Only after the independently attested synthetic source proof is restored may an exact replay return 200 `DEAD` with `idempotent=true` and the same receipt SHA256.

## Qualification

`tests/test_core_hitl_reject_terminal_pg16.py::CoreTerminalPopulatedPG16.test_terminal_canonical_http_postcommit_revocation_fails_closed` exercises the actual Core app with installed disposable PostgreSQL 16 migrations 001/004/009–014. The dedicated workflow requires 15/15 tests with zero skips and verifies `terminal-postcommit-revocation.json`, `payload_sha256`, exact checkout SHA, secret redaction, no positive human GLPI authorization, and audit-preserving rollback.

No new migrations, no GLPI write, no Worker/Portal edits, no host deployment, no `ALLOW`, no LIVE. Existing native PostgreSQL 16 archive/restore and 013/014 immutability checks remain mandatory in the same dedicated test suite. **Rollback: revert only this focused test/workflow/ADR delta; never DOWN/DROP or modify immutable 013/014 audit rows.**

`actor_authorization=UNKNOWN`; `link_status=UNKNOWN`; `RELEASE_STABLE=NO_GO`.
