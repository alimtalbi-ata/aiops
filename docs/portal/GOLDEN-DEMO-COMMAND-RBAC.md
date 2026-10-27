# Golden DEMO command guard (P0)

The legacy `POST /api/demo` creates a synthetic Incident, a DEMO Run, and requests its execution through Core. Previously the public portal exposed this write operation without authentication. This change adds a **mandatory operator Bearer token** before any Core call. It does not authorize LIVE actions.

- `AIOPS_PORTAL_OPERATOR_TOKEN`: 32–256 printable, non-whitespace ASCII characters; configure via a protected secret on the portal container. Never reuse `AIOPS_INTERNAL_TOKEN`, `AIOPS_ADMIN_TOKEN`, or a viewer token.
- Unconfigured or colliding operator/viewer token: HTTP 503, no Core call.
- Missing, viewer, wrong or malformed Bearer: HTTP 401, no Core call.
- The portal clears the password input before sending, does not persist it in browser storage, and never renders the token in the response.
- Successful request remains explicitly `DEMO` with `synthetic: true`; the UI labels the result `DEMO_CREATED_UNVERIFIED`, not a LIVE success.
- `/health` stays accessible for container health probes.
- This is a **scoped hardening**, not global authentication. The legacy homepage, bootstrap and Copilot routes still require RBAC design; the operator read-only UI is being developed separately in PR #51.

## Verification and deployment constraints

`python -m unittest discover -s tests -p 'test_portal_demo_command_auth.py' -v` exercises FastAPI TestClient with in-process replacement of Core calls; it does **not** qualify a real Core/Temporal service. The existing `quality.yml` invokes these tests. No Debian runtime, production credentials, Checkmk/Thruk, GLPI, Grafana, n8n, or real NIM were contacted.

Ported safety principles from PR #36's `noc_runtime.py`: explicit credentials, fail-closed missing configuration, bounded credential format, and no upstream call before authorization. No broad PR #36 merge.

Rollback: revert this focused PR if needed; do not replace the operator token with a hardcoded/demo value. If not configured, the DEMO action intentionally remains unavailable.
