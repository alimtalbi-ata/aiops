# Automation run — 2026-10-28 00:40 Europe/Paris — P1 ACME / ITSM

## Starting state and review

- Repository: `alimtalbi-ata/aiops`; verified latest `main` SHA at start: `0603e86a26978873c3b6196098674932d3378499` (GitHub commit search).
- Reviewed open PRs #36, #37, #39, #41, #43 and current #56, plus merged #50 and closed #53.
- Read `docs/PROJECT-CONTINUITY.md`, `docs/ARCHITECTURE-AND-BOUNDARIES.md`, `docs/DECISION-LOG.md`, `docs/COMPONENT-CATALOG-AND-REUSE.md`, existing ACME fixture/impact module, NOC signed read model, Compose and quality workflow.
- Inspected PR #36 `demo/noc_topology.py` at SHA `f353497f46876792a6e7d6e85a36397c4aac8090`; its synthetic topology duplicates the already ported ACME impact graph and contains no authenticated GLPI reader. Avoided mass merge or duplicate topology.

## Delivered increment

- Branch: `feat/acme-glpi-readonly-ticket-contract-20261028` from the exact starting SHA.
- Draft PR: https://github.com/alimtalbi-ata/aiops/pull/69
- New `app/shared/glpi_ticket_read.py`: bounded authenticated GLPI API GET, explicit numeric ticket identity, tenant entity fence, strict JSON and response validation, redirect/proxy refusal, HTTPS outside isolated CI, explicit DEMO/SIMULATION-only mode, LIVE refused before any network request. Read-only, not mounted into public Portal.
- New `tests/test_glpi_ticket_read.py`: 16 offline unit tests, including negative security, identity, tenant, LIVE mode and secret redaction cases.
- Updated `.github/workflows/quality.yml` (existing workflow; no parallel CI), `docs/demo/ACME-GLPI-READONLY-TICKET-CONTRACT-20261028.md`, `docs/DECISION-LOG.md`, `docs/PROJECT-CONTINUITY.md` and this run journal.
- Commits: `e5a7b461` code, `55bcb181` tests, `557fe034` CI, `02d68c20` docs, `e21e3599` ADR, `89de7125` mode guard, `21034c07` mode tests, `5a40ca9f` docs, `41a6e97d` continuity.

## Tests and evidence

- GitHub Actions **executed** on SHA `e21e35994bd172c7e92d3a513a1d75e39d56b564`: https://github.com/alimtalbi-ata/aiops/actions/runs/40603991468 — **SUCCESS**; job `policy-and-static` including GLPI contract step, compileall, ACME impact, NOC, policy, static audit, Compose config all green.
- GitHub Actions **executed** on mode-fence test SHA `21034c074fb1da07624253dc107f2dc36b73898c`: https://github.com/alimtalbi-ata/aiops/actions/runs/40604035673 — **SUCCESS**, including the GLPI test step. Docs-only SHA `5a40ca9fea9dd6b5a254f44ddd15547dc69c7839` also passed: https://github.com/alimtalbi-ata/aiops/actions/runs/40604050727. Later journal/continuity HEAD was not yet confirmed complete at the time of this update. No local test execution (GitHub connector files not locally mounted).
- GLPI+MariaDB real ephemeral service: **NOT_TESTED**. NIM/Ollama: not exercised by this lot. Actual NOC/Core/GLPI E2E, Debian, LIVE, ticket provenance and screenshots: **NOT_TESTED**.

## Risks / blockers / next micro-lot

- Public Portal and GLPI live on different Compose networks. Never connect Portal directly to integration network. Need a narrowly scoped authenticated read-only bridge with tenant and identity binding.
- GLPI REST API needs an initialized real test instance, enabled API, pre-provisioned app/session tokens and a test ticket in an isolated tenant. No credentials or production tokens in GitHub.
- PR #56 signed NOC/Core correlation is still draft; future integration must wait for its safe merge or selectively port its contracts.
- Next: confirm quality.yml on latest head, fix failures, then add GLPI ephemeral integration qualification and a bounded cross-reference receipt. No merge/deploy/LIVE action in this run.
