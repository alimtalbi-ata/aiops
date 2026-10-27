# Security and secrets

## New installations

`deploy/install.sh` creates a new `.env` with cryptographically random values using OpenSSL, sets file permissions to `0600`, and uses the same generated internal token for `AIOPS_ADMIN_TOKEN` and `AIOPS_INTERNAL_TOKEN` because current service authentication expects them to match. It also generates a separate `AIOPS_PORTAL_READ_TOKEN` used only to authorize `GET /api/portal/bootstrap`; the token is never printed or reused as the internal/admin token.

If `.env` already exists, the generator does not rotate or overwrite it. Preflight rejects missing/default demo secrets unless the operator explicitly sets `AIOPS_DEMO_MODE=1`. Fix an existing environment deliberately; do not rotate a database password without coordinating the database's stored credentials and a rollback plan. The preflight failure message is deliberately plain text (no shell command substitution) so the diagnostic itself cannot execute a command.

## Demo mode

The secure `config/.env.example` intentionally leaves secret values blank; the installer fills them with random values. `config/.env.demo.example` contains known sample values for an isolated, disposable local demo only. To deliberately opt into those values, copy that file to `.env` and keep `AIOPS_DEMO_MODE=1`. Never use this option for shared, internet-facing, staging or production environments. Demo mode emits a warning during preflight.

## Production requirements

- Keep `.env` out of source control and restrict it to the deployment account.
- Use unique random secrets and a secret manager/Docker secrets for production deployments.
- Never print credentials in diagnostics, commit them outside the documented demo template, or copy them into logs/screenshots.
- The n8n sample workflow may contain a demo token for local demonstration; production imports must replace it with an n8n credential.
- Secret rotation must account for PostgreSQL, GLPI, Grafana, n8n and internal service consumers; do not rotate a live credential without a coordinated plan.


## Optional signed NOC source

The NOC read-model bridge is disabled unless all four settings are explicitly provided: endpoint URL, upstream Bearer token, HMAC-SHA256 key and exact allowed origin(s). The upstream token and HMAC key are separate credentials, provisioned out-of-band; the installer never generates or prints them. The preflight permits the bridge to remain entirely unset, but rejects partial configuration, short credentials and endpoint origins that do not exactly match the allowlist. Keep any configured values in the mode-0600 .env or a supported secret manager; never place them in Git, the candidate ZIP, logs or screenshots.

The portal sends the upstream token only to the allowlisted origin, disables ambient proxy configuration, follows no redirects, and accepts a response only after its exact bytes pass both SHA-256 and HMAC verification. This authenticates the signed payload, not the truth of a ticket, timestamp or application screenshot. Runtime attestation and LIVE remediation remain false.
