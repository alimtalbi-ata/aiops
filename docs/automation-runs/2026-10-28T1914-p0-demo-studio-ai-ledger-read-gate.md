# P0 NOC/Copilot — Demo Studio AI ledger read gate — 2026-10-28 19:14 Europe/Paris

## Source and concurrency
- Checked `main` HEAD `793a5a03688dcb7c1a689d07e31bea770da4bd4f`; delivery branch `feat/demo-studio-v2-delivery-20261028` HEAD `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3` before modification. This branch is a different code lineage from main; PR targets the delivery branch, not main.
- Reviewed open PRs including #36/#37/#39/#41/#43, #133/#139 and #127/#128; latest Explore/Story and Core NOC journals, continuity/decision log and the delivery branch's `quality.yml`. Reused the existing Core ledger API, shared HTTP client, Demo Studio UI and the tenant-scope refusal helper already on main; no bulk merge.
- Branch `fix/demo-studio-ai-ledger-read-gate-20261028-1914`, owned NOC/Copilot scope. No other branch modified.

## Vertical delivery and API contract
- `app/portal/demo_ledger_read.py`: GET `/api/demo-studio/runs/{rid}/ai-ledger` (`aiops.demo-ledger-read.v1`), viewer Bearer `AIOPS_PORTAL_READ_TOKEN` required **before upstream I/O**. Viewer token must be distinct from `AIOPS_INTERNAL_TOKEN`; Core is called server-to-server using the existing `shared.http.get_json` internal token. Never expose Core token to browser.
- 200: bounded allowlisted analysis/critique/Policy projection, canonical Run ID, DEMO/REPLAY/STORY only, source `CORE_AI_LEDGER_INTERNAL_READ`, `runtime_attested=false`, `tenant_acl_qualified=false`. 401: invalid/missing viewer token. 503 UNKNOWN: viewer misconfiguration, upstream Core 401/timeout, missing/mismatched source, tenant claim, malformed/oversized ledger or LIVE Run. `Cache-Control: no-store`. No write, no execution, no claims of real LLM quality.
- `app/portal/main.py`: stop anonymous SSR/polling reads of the AI ledger; Demo Studio detail displays an opt-in viewer-token read panel with redacted errors, token cleared from the input immediately. Legacy Run/gate/Twin pages remain outside this narrow gate.
- `app/shared/tenant_scope.py`: targeted port from main's already merged conservative scope refusal (no tenant ACL). `tests/test_demo_ledger_read.py`: 9 unit-only tests including upstream 401, invalid/missing viewer, LIVE, cross-tenant, mismatched Run, missing source, non-disclosure and legacy SSR regression. `.github/workflows/quality.yml`: one additional test step in the existing workflow; no parallel CI.
- Changed files: `app/portal/demo_ledger_read.py`, `app/shared/tenant_scope.py`, `app/portal/main.py`, `tests/test_demo_ledger_read.py`, `.github/workflows/quality.yml`, this journal.

## Qualification and limits
- Local isolated unit harness: 8 tests passed on the new adapter using a **stubbed shared HTTP client**; this is unit-only, **not Core integration**. Ninth source-regression test is for the committed portal patch and will run in GitHub CI.
- GitHub Actions `quality.yml`: PENDING on the new commit; **do not mark PASS** until its exact run and jobs are confirmed. The delivery branch's existing runtime-e2e uses a deterministic test provider, **not** Ollama 4B or NGX. No equivalent LLM-quality claim.
- NOT_TESTED: Core/PostgreSQL ledger integration with two tenant identities, real Grafana SAN metrics, Twin Payments impact, Checkmk/Thruk, Ollama 4B, authenticated browser capture, Debian runtime, client E2E. Existing anonymous Core Run/Twin/gate reads still need separate RBAC work.
- Risk: internal token mismatch between Portal and Core can still produce Core 401; the new route reports UNKNOWN/503 rather than fixing deployment secrets. Provision a distinct viewer secret through authorized deployment only. The read gate is **not** tenant authorization.
- No Debian access, deployment, production secrets, NGX call, LIVE remediation, or merge.

## Next micro-lot
Qualify this read-only route against real ephemeral Core/PostgreSQL with an actual AI ledger and 401 negative case, then bind authenticated actor/tenant A/B before any observed SAN/Payments metrics or RAG retrieval.

## Configuration et commit de suivi
- Commit initial `888b6a62f523d1f0a223dff8591ab154d785e3f4`; [PR draft #145](https://github.com/alimtalbi-ata/aiops/pull/145), base `feat/demo-studio-v2-delivery-20261028`. CI initiale [run 40743763294](https://github.com/alimtalbi-ata/aiops/actions/runs/40743763294) : QUEUED lors de la vérification, aucun PASS revendiqué.
- Wiring ajouté dans `compose.yml`, `config/.env.example` et `deploy/init-env.sh` : variable viewer distincte, génération aléatoire uniquement lors d'une **nouvelle** installation locale ; installations existantes conservées et laissées fail-closed tant que l'opérateur ne configure pas une valeur distincte. Aucun secret ni changement sur Debian.
- Tests : ajout du contrôle statique de la configuration au fichier de tests (10 tests unitaires prévus dans `quality.yml`). CI sur le commit de suivi : PENDING, vérifier SHA exact et jobs avant fusion.
- Contrat : la lecture nécessite `AIOPS_PORTAL_READ_TOKEN` côté serveur et un Bearer viewer saisi volontairement dans le navigateur ; le jeton interne Core n'est jamais transmis. Ce n'est pas un SSO ni une ACL tenant.
