# P0 NOC — Core authenticated synthetic read, 2026-10-28 11:08 Europe/Paris

- **Starting main SHA:** `723ca6458c722a1aa0e57ddb5eee3374d20cc830`; new branch `fix/p0-noc-core-read-auth-real-ci-20261028-1108`, independent of other slots.
- **Source review:** main, draft PR #36/#37/#39/#41/#43, `docs/PROJECT-CONTINUITY.md`, architecture, reuse matrix, decisions and existing `.github/workflows/quality.yml`. Targeted reuse: PR #36's synthetic-only NOC boundary via the signed NOC code already integrated in main; no mass merge.
- **Changed files:** `app/shared/tenant_scope.py`, `app/portal/noc_runtime.py`, `app/core/main.py`, `app/portal/noc_correlation.py`, `tests/test_noc_canonical_correlation.py`, `tests/test_core_noc_real_integration.py`, `.github/workflows/quality.yml`, `docs/PROJECT-CONTINUITY.md`, `docs/DECISION-LOG.md`, this journal.
- **Code:** authenticated Core read-only projection of synthetic Run/Incident; denies LIVE, observed Incident, missing source, nested tenant claims and bad auth. Portal no longer uses the unprotected full Core Run endpoint for NOC correlation. No writes on the new route.
- **Tests:** existing contract tests and a new real Core + PostgreSQL 16 HTTP job added to existing quality workflow. **PENDING GitHub Actions; no PASS claimed at commit creation.** No Checkmk/Thruk, Grafana metrics, Ollama, NGX, tenant A/B authorized read or Debian test.
- **Risk:** legacy Core read endpoints remain unprotected; the internal service token is not tenant/actor identity; PostgreSQL has no canonical tenant column. No observed data is authorized for correlation.
- **Commits/PR/CI:** to be filled after GitHub confirms exact SHA and run.
- **Next micro-lot:** Core-owned authenticated actor/tenant identity and real two-tenant A/B authorization tests; then observed Checkmk/Thruk and Grafana metric provenance.
- **Safety:** no production credentials, Debian access, deploy, merge, NGX call, remediation or LIVE command.
