# AIOps 2.0 — Deployment, Qualification and Recovery Runbook

**Author:** Abdelhalim Talbi  
**Scope:** Debian 13 / Docker Compose single-host installation. Use a disposable host for qualification before any production rollout.

## Standard install (never retires legacy services)

From the extracted cumulative kit root:

```bash
bash deploy/install.sh
```

The installer generates `.env` only when absent, validates secrets and host prerequisites, validates Compose, builds all declared images, starts services, runs additive schema migrations, qualifies service health and runs the synthetic E2E test. An existing `.env` is not rotated automatically. Inspect any failure and preserve the diagnostic output; do not repeat a failed install blindly.

## Fast operator commands

```bash
bash deploy/preflight.sh
docker compose --env-file .env config --quiet
docker compose --env-file .env ps --all
bash deploy/migrate.sh
bash tests/qualification.sh
bash tests/synthetic-e2e.sh
bash deploy/diagnose.sh
bash deploy/backup.sh
bash deploy/package.sh
```

Generated diagnostics go under `reports/`. Review redacted logs before sharing. A diagnostics bundle intentionally excludes `.env`, database dumps and other private recovery material.

## Migration contract

- PostgreSQL initdb executes migrations only for a new volume.
- `deploy/migrate.sh` is the explicit additive upgrade path for an already initialized database.
- The runner verifies a signature of the 000–008 schema before recording those migrations as a baseline; if the schema is partial or unknown, it fails closed rather than guessing.
- Every applied migration from 009 onward is recorded in `public.aiops_schema_migrations` with SHA-256. Re-running is idempotent; checksum drift on an applied migration is an error.
- Never edit an applied migration. Add the next numbered migration.
- Before upgrading an existing host, take and verify a database backup and inspect the exact schema signature. Do not use destructive volume deletion as a migration strategy.

## Recovery

1. Stop and preserve the failed host state if the failure could involve data corruption.
2. Create a separate diagnostics bundle and keep it private until redaction is reviewed.
3. Confirm the backup's `SHA256SUMS`, database version, Git commit and target environment.
4. Restore only into a deliberate recovery target. The restore script requires both `CONFIRM_RESTORE=YES` and `CONFIRM_TARGET_DATABASES=YES`.
5. Run the migration runner, then service qualification and synthetic E2E.
6. Compare run counts, latest run versions, event/evidence counts and AI ledger integrity with the pre-incident inventory.
7. Do not declare recovery successful based solely on PostgreSQL accepting a dump; confirm application semantics and a replayable incident scenario.

Backups include database dumps and a private `.env`; they contain secrets and must be encrypted at rest and stored outside GitHub. The scripts do not upload backups anywhere.

## Cumulative ZIP

`bash deploy/package.sh` runs static, SQL and ledger-contract audits, compiles Python, archives the committed Git tree, adds a release manifest and per-file checksums, and emits a ZIP plus SHA-256 under `dist/`. The package excludes `.env`, Git metadata, caches, backups and diagnostic reports. Package only a committed and CI-qualified branch.

GitHub Actions builds every application image, runs unit/static tests, applies the full SQL chain to disposable PostgreSQL, exercises the upgrade runner against a legacy-only schema, and publishes the ZIP as an artifact. The artifact is a build package, not evidence of successful production installation or real-model quality.

## Core AI evaluation

Configure the provider in local `.env`, start the stack and verify `/ready` reports ready. Then run:

```bash
AIOPS_INTERNAL_TOKEN="$(grep '^AIOPS_INTERNAL_TOKEN=' .env | cut -d= -f2-)" \
INTELLIGENCE_URL=http://127.0.0.1:817 \
python3 tools/evaluate_intelligence.py
```

This sends only synthetic fixtures to the configured endpoint and produces a timestamped JSON report under `reports/`. If the provider is unavailable, the result is `NOT_RUN`, not PASS. The evaluator checks expected severity, evidence-ID grounding, advisory-only actions and Critic validation. A model can fail the golden set; tune prompts/contracts and rerun the suite rather than weakening the checks without a documented decision.

## Safety boundaries

- No production test is part of the standard CI pipeline.
- LIVE stage adapters and actual effect execution remain disabled until real evidence acquisition, policy, fencing/ownership, human approval, idempotent effect receipts, independent verification and reconciliation are qualified.
- Approval records bind to the immutable proposal hash and exact target/action scope. CRITICAL proposals require two distinct approvers with distinct roles.
- Synthetic modes cannot create real approval records. Synthetic or unreviewed cases cannot enter the trusted gold set.
- Never share `.env`, raw database dumps, provider keys or unredacted logs.
