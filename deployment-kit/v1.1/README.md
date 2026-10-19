# AIOps 2.0 Deployment Kit V1.1 (reference)

This directory records the deployment and Temporal safety kit used for the 2026-10-19 read-only audit. It is not a self-contained application build and does not contain the missing Core/Worker/Policy/Intelligence/RAG/Twin/Simulator/Evidence service sources.

## Qualification result

- Archive SHA-256: `3c22ef388abaea3263a38f3403221892f0e6b8b06e0d130bb8f39a5b5f4fd5cf`
- Runtime audit: completed.
- Preflight: **FAIL** — Docker's Compose label points to `/home/aiops/aiops2-v8-r4/00-Deployment/compose.yml`, which was absent when the script ran.
- Deployment: not run.
- Production: unchanged by the audit.

Do not execute `deploy.sh --apply` until the real Compose path, all overrides, images, service selection and rollback plan have been verified. Never recreate a missing production Compose file from assumptions.

## Files

- `scripts/audit-runtime.sh` — read-only runtime inventory.
- `scripts/preflight.sh` — fail-closed prerequisites and Temporal route check.
- `scripts/deploy.sh` — plan/apply guard; no build, no Temporal/database redeployment.
- `config/temporal-routing.env.example` — proposed routing for new V2 workers only; do not overwrite active worker configuration without a reviewed change.
- `docs/ARCHITECTURE-CIBLE.md` — target orchestration, ACME twin, simulation, evidence and safety invariants.

Never commit live secrets, environment files, credentials, database dumps or production exports.