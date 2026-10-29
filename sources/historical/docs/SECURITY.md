# Security and secrets

## New installations

`deploy/install.sh` creates a new `.env` with cryptographically random values using OpenSSL, sets file permissions to `0600`, and uses the same generated internal token for `AIOPS_ADMIN_TOKEN` and `AIOPS_INTERNAL_TOKEN` because current service authentication expects them to match. Generated values are never printed.

If `.env` already exists, the generator does not rotate or overwrite it. Preflight rejects missing/default demo secrets unless the operator explicitly sets `AIOPS_DEMO_MODE=1`. Fix an existing environment deliberately; do not rotate a database password without coordinating the database's stored credentials and a rollback plan.

## Demo mode

The secure `config/.env.example` intentionally leaves secret values blank; the installer fills them with random values. `config/.env.demo.example` contains known sample values for an isolated, disposable local demo only. To deliberately opt into those values, copy that file to `.env` and keep `AIOPS_DEMO_MODE=1`. Never use this option for shared, internet-facing, staging or production environments. Demo mode emits a warning during preflight.

## Production requirements

- Keep `.env` out of source control and restrict it to the deployment account.
- Use unique random secrets and a secret manager/Docker secrets for production deployments.
- Never print credentials in diagnostics, commit them outside the documented demo template, or copy them into logs/screenshots.
- The n8n sample workflow may contain a demo token for local demonstration; production imports must replace it with an n8n credential.
- Secret rotation must account for PostgreSQL, GLPI, Grafana, n8n and internal service consumers; do not rotate a live credential without a coordinated plan.
