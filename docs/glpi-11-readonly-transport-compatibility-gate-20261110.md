# GLPI 11 read-only transport compatibility gate (2026-11-10)

## Observed repository contract

Historical `app/portal/glpi_client.py` at `5b3b9f327f517e8f5999766389abf69c8a035cf8` used the GLPI REST `/apirest.php` API:

1. GET `/initSession` with server-owned `App-Token` and `Authorization: user_token <token>`.
2. GET `/Ticket/{ticket_id}` with `App-Token` and `Session-Token`.
3. GET `/killSession` for cleanup.

The historical client also exposed ticket creation and update. **Do not restore its write methods** for this P0 read-only qualification.

## Current PR #520 gap

`shared.glpi_http_json_transport.make_json_get` currently supports only `Authorization: Bearer <token>`. The assembly in `shared.glpi_server_readonly_assembly` therefore **does not implement the historical GLPI REST session contract**. Its green tests mock GET responses and cannot establish GLPI 11 authentication compatibility. The Core service authentication mechanism also requires independent deployment verification.

**Block real installation** until a read-only GLPI session adapter has been built and tested against a disposable GLPI 11 instance with a dedicated least-privilege service account, explicit HTTPS origin, no redirects, no environment proxies, bounded responses and session cleanup. The adapter must never expose tokens to Portal users, and must never provide POST/PUT/DELETE ticket operations.

## Additional independent gates

- Protected signed-event producer and verified event storage for the canonical xref.
- Durable atomic PostgreSQL nonce replay store and server-owned actor/tenant ACL.
- Real Core/GLPI readback and entity/tenant scoping, with negative ACL tests.
- Authenticated Portal identity mapping; the Portal viewer token is **not** an actor ACL.
- E2E checks for historical GLPI→Copilot and HITL navigation without granting execution.

No merge, Debian deployment, GLPI writes or production authorization is implied by offline CI.
