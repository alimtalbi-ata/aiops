# AIOps 2.0 Platform Foundation V2.0.0

Author: Abdelhalim Talbi

Clean rebuild, not a restoration of the missing V2 deployment directory. New isolated Compose project; legacy runtime is preserved.

## Working vertical slice
- FastAPI incident intake, listing, readiness and analysis API.
- PostgreSQL persistence with idempotency.
- Deterministic fail-closed policy; automatic remediation disabled.
- Isolated Docker Compose, health checks, smoke tests, backup and diagnostics.
- YAML/JSON examples, roadmap and SHA-256 manifest in the cumulative ZIP.

## Explicit gaps
Temporal durable workflows, LLM analyst/critic, RAG, GLPI/HITL, CMDB reconciliation, chaos engine and production SSO are roadmap integrations, not claimed complete.

Use the cumulative chat artifact `AIOps2-Platform-Kit-V2.0.zip`, verify its SHA256, then run `scripts/one-shot.sh --check` and `scripts/one-shot.sh --install`. It refuses to overwrite an existing destination and uses isolated project name `aiops2-v2`.

Runtime qualification must be performed on Debian. Never commit `.env` or runtime data.