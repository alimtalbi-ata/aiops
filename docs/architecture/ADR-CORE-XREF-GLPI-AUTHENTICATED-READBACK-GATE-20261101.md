# Core xref v1 — authenticated GLPI read-back gate (2026-11-01)

Scope: Core-owned read-only `GET /api/tenants/{tenant_id}/itsm/glpi/{instance_id}/tickets/{ticket_id}/xref`; no API/schema/migration changes. This focused change is based on the sole Draft #234 candidate, not historical #205/#233/#238.

## Authority and server configuration

`AIOPS_XREF_GLPI_READBACK_JSON` is a **server-only** JSON array (maximum 16 exact tenant/instance bindings). Each entry contains exactly `tenant_id`, `instance_id`, `origin`, `app_token`, `session_token`. The origin must be a pinned HTTPS scheme/host, with no path, query, userinfo or fragment. Secrets must be injected by the trusted deployment and never sent to clients or logged. Never use a user-supplied URL, proxy, redirect, or GLPI write. The GLPI session must have least-privilege **read** rights for the scoped entity and CI.

The positive Core xref result now additionally requires these authenticated, exact GLPI API reads:

- `GET /apirest.php/Ticket/{ticket_id}`: numeric ticket ID and `entities_id` must match the signed xref event.
- `GET /apirest.php/Entity/{glpi_entity_id}`: exact entity ID must exist in the scoped GLPI session.
- `GET /apirest.php/Ticket/{ticket_id}/Item_Ticket`: nonempty, bounded set of directly attached CIs; no ambiguous or duplicate records.
- `GET /apirest.php/{allowlisted_ci_type}/{ci_id}` for each attached CI: exact CI ID and entity must match.

GLPI HTTP 200 + JSON is insufficient by itself: redirects, unexpected types, malformed/oversized payloads, missing attached CI, wrong entity, stale signed event, missing server ACL, missing independent owner HMAC, or Run→Incident mismatch all fail closed to `UNKNOWN` without business identifiers. The GLPI adapter uses pinned HTTPS with certificate verification, a three-second read timeout, no ambient proxies and no redirects. No HTTP request occurs before Core service authentication and server-side tenant/permission checks.

**Limits:** This proves source ticket/entity/CI *existence and scope at read time*, not that a GLPI ticket itself contains a canonical Run association. The append-only Core signed mapping and exact Core Run→Incident are still separate requirements. The static service-token actor is not a delegated OIDC human grant; therefore human actor authorization remains **NOT_ATTESTED**, and Portal must not treat this as a positive human ACL. No real GLPI credentials or authenticated GLPI read were used in this change. No GLPI writes, no production DB, no LIVE.

## Qualification and rollback

Unit tests mock the GLPI REST transport and test tenant/instance mismatch, wrong ticket/entity/CI, empty attachment, redirect, and HTTP hardening. Disposable PostgreSQL 16 tests intentionally expect `UNKNOWN` for synthetic signed records without an independently configured GLPI source. This is a security tightening, not a real GLPI integration test.

Migration chain `001→004→009 AI→010 Evidence→011 HITL→012 xref` is unchanged; architect-owned exact-head CI has already exercised transactional DDL rollback and idempotence. **Persistent data downgrade is still NOT_QUALIFIED** and must be planned separately; never claim that a DDL transaction rollback validates populated-table downgrade. Revert the focused Core and tests commit(s) to roll back this gate; no database migration or data rewrite is required.

Related: #186, #203, #205, #234, #61, #65. `link_status=UNKNOWN` until an authenticated, tenant-scoped Core and GLPI read-back is actually observed. `RELEASE_STABLE=NO_GO`.
