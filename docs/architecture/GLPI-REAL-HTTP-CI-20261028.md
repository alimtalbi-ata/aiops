# P1 — GLPI real HTTP negative integration (2026-10-28)

## Scope and provenance

Stacked on draft PR #69, which contains the read-only `shared.glpi_ticket_read` adapter and offline contract tests. This micro-lot changes only the existing `.github/workflows/quality.yml`, adds `tests/test_glpi_real_http.py`, and documents the qualification boundary. No mass merge of PR #36 or duplicate CI workflow.

GitHub Actions starts the repository's **real** `glpi/glpi:11.0.9` and `mariadb:11.4` Compose services with newly generated ephemeral CI credentials. A separate read-only Python client container joins the isolated `aiops2-integration` network. No real NGX endpoint or production secret is used; no LLM is exercised.

After GLPI/MariaDB startup, the job enables the **legacy REST API only in this disposable GLPI container** via the official `php bin/console config:set enable_api 1` command (no production configuration). The test waits for the real GLPI HTML frontend, sends an HTTP GET to the real `/apirest.php/Ticket/2147483647` endpoint with deliberately invalid CI-only tokens, and requires a structured GLPI API authorization rejection. It then checks that the actual read-only adapter returns `GLPIUnverified`. LIVE is rejected by the adapter's mode guard. If GLPI does not initialize, the ephemeral REST API cannot be enabled, the response is HTML, or the denial cannot be distinguished, the job **fails**, never silently substitutes a mock.

## What this does not prove

- **No successful ticket read:** there is no provisioned GLPI app/session token, no created ticket, and no observed Incident/Run/ticket binding.
- **No positive end-to-end integration:** Core, Temporal, portal, real GLPI ticket creation and RBAC are NOT_TESTED.
- **No production/LIVE qualification:** only isolated CI HTTP and contract-level refusal.
- **No 192B model quality equivalence:** this job does not call any LLM. Other integration services are not silently simulated.
- **No Debian access:** only ephemeral GitHub runner containers.

## Test/rollback

`quality.yml` retains its existing jobs and adds one opt-in-by-PR job, `glpi-real-http-negative-integration`, which starts actual services and removes their ephemeral volumes in the `always()` cleanup step. Revert the workflow job and `tests/test_glpi_real_http.py` to roll back. A CI success proves only the described negative HTTP path, not positive ticket correlation.

Next micro-lot: provision GLPI API credentials **inside isolated CI only**, create and read a disposable ticket, assert entity isolation, then independently verify Core Incident/Run binding and connect the portal behind server-derived RBAC.

## CI evidence (code HEAD 2026-10-28 10:49 Europe/Paris)

- [GitHub Actions 40667157033](https://github.com/alimtalbi-ata/aiops/actions/runs/40667157033): `completed/success` on `6dc9ce5e632a1d45817420ba90e045b7176052a5`; 4 real-HTTP negative tests, existing GLPI offline contract tests, static audit and Compose configuration succeeded.
- Prior failures are preserved, not hidden: [40665784889](https://github.com/alimtalbi-ata/aiops/actions/runs/40665784889) (HTML preview length assumption), [40666629463](https://github.com/alimtalbi-ata/aiops/actions/runs/40666629463) (real API disabled by default), [40666980666](https://github.com/alimtalbi-ata/aiops/actions/runs/40666980666) (API disabled; actual JSON response). The fixes were made on this branch.
- Final documentation-only HEAD will be checked separately; the above success is the verified **code HEAD**.
