# Internal GLPI read gateway (stacked on PR #69)

**Qualification:** SOURCE + OFFLINE CONTRACT TESTS only; real GLPI container API access **NOT_TESTED**. No Debian deployment or LIVE action.

The optional `aiops2-glpi-reader` service uses the real `shared.glpi_ticket_read.read_ticket` adapter from PR #69 and is on `aiops2-control` and `aiops2-integration` only. There is no `ports` mapping. Profile `glpi-readonly-ci` must be explicitly selected; it is **not** enabled by default. The public Portal has no end-user RBAC integration for this gateway and **must not** proxy it yet.

`GET /internal/glpi/tickets/{numeric_ticket_id}?mode=DEMO` requires `Authorization: Bearer <AIOPS_GLPI_READER_TOKEN>` (32–512 safe characters). `SIMULATION` is also accepted; `LIVE`, `REPLAY`, `STORY`, and unknown modes are refused before GLPI I/O. A successful upstream read returns `OBSERVED_UNCORRELATED`, not an Incident/Run match or a production attestation. Errors return `UNKNOWN` with no ticket identifier or credentials.

The container requires separately provisioned `AIOPS_GLPI_API_BASE_URL`, `AIOPS_GLPI_APP_TOKEN`, `AIOPS_GLPI_SESSION_TOKEN`, `AIOPS_GLPI_ENTITY_ID` and `AIOPS_GLPI_READER_TOKEN`. Tokens must come from a secret manager or isolated CI ephemeral environment, never from committed files. No `initSession`, ticket writes or ticket creation is implemented. Outside CI the adapter requires HTTPS; isolated CI HTTP is restricted to `http://aiops2-glpi/apirest.php`. Do not set `CI=true` to bypass transport restrictions in production.

`quality.yml` executes offline auth/negative tests and `docker compose --profile glpi-readonly-ci config`; this validates configuration, **not** real GLPI API behavior. An actual containerized GLPI qualification must initialize a disposable GLPI instance, provision an ephemeral API session and ticket, verify tenant scoping and negative mismatches, then destroy the instance. Do not label offline `unittest.mock` tests as integration. Never connect a public Portal route before identity/RBAC and independent Core correlation are established.

## Dependency and rollback

This is a **stacked PR** based on PR #69's `feat/acme-glpi-readonly-ticket-contract-20261028`; merge/rebase that dependency first after its checks are green. Rollback consists of disabling the optional profile or reverting the gateway change; no database migrations or writes exist. The ACME SAN→ESXi→VM→Payments synthetic impact view on main is unchanged.
