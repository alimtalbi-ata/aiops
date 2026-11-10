# n8n integration pack

n8n is an integration boundary, not the canonical Run Engine. Workflows must call the Portal/Core APIs and never write the AioOps PostgreSQL tables directly.

## Disabled incident template

`incident-to-run.json` is a **disabled, fail-closed example**. It contains only an incoming webhook and a static `HOLD` response (`N8N_TEMPLATE_DISABLED`); it does not create incidents, start runs, or execute LIVE actions. It is intentionally importable rather than auto-imported. **Do not activate it or treat a successful import as authorization to run it.**

Never embed API tokens, including demo tokens, in exported n8n workflows. A future operational integration requires trusted caller identity, tenant-scoped authorization, managed credentials, independent security review, and explicit signed approval before deployment or activation.

An earlier committed version of this template contained a credential and a LIVE-capable path. Removing those fields from the current template does not revoke the historical credential or remove copies from Git history. Track credential revocation/rotation, usage audit, and copy/history assessment in security issue #535; keep production and LIVE operations on HOLD until the authorized security owner documents clearance.
