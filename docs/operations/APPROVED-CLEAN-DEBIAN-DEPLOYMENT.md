# Approved clean Debian deployment from GitHub Actions

**Status:** Controlled first-install automation; not an in-place upgrade workflow.  
**Workflow:** `.github/workflows/deploy-clean-debian.yml`  
**Target:** A new, empty Debian 12 host.  
**Approval:** GitHub Environment `aiops-debian-lab` must be configured with required reviewers.

## Purpose and safety boundary

This workflow transfers a reviewed source snapshot to a Debian 12 host over SSH, runs the repository's canonical `deploy/install.sh`, and collects sanitized deployment evidence.

It is deliberately restricted to **first installation into a path that does not exist**. It will refuse to overwrite an existing directory, existing AIOps installation, or persistent volumes. It does not deploy to SRV-DEB-05 by default and must not be repurposed as an in-place upgrade workflow.

No automatic rollback or volume deletion is performed. If installation or qualification fails, the target directory, generated host-local `.env`, containers and volumes are retained for diagnosis. An operator must inspect the failure and decide the recovery action. This is safer than deleting state whose consistency has not been proven.

## GitHub configuration

Create a GitHub Environment named `aiops-debian-lab`:

1. Require at least one reviewer before the deployment job starts.
2. Restrict deployment branches/tags to reviewed release candidates.
3. Add these environment-scoped secrets:
   - `DEPLOY_SSH_HOST`: DNS name or IP of the clean Debian 12 host.
   - `DEPLOY_SSH_USER`: non-root account with Docker access.
   - `DEPLOY_SSH_PRIVATE_KEY`: private key dedicated to this workflow.
   - `DEPLOY_SSH_KNOWN_HOSTS`: pre-verified SSH host-key line(s), obtained out-of-band.
4. Do not use `ssh-keyscan` in the workflow as a trust-on-first-use substitute.
5. The SSH account must have sufficient disk space (>8 GiB per current preflight), Docker Engine and Compose v2 already installed, and permission to create the selected target path.

Never put the private key or host credentials in repository files, workflow inputs, or deployment artifacts.

## Run

From GitHub Actions, select **Approved clean Debian deployment** and manually dispatch it with:
- `source_ref`: reviewed branch, tag or immutable commit SHA;
- `target_root`: absolute path that does not yet exist, for example `/home/aiops/aiops2-v8`.

The workflow checks the host is Debian 12, the SSH user is not root, Docker/Compose are usable, free space is sufficient and the target path is absent. It then transfers a source archive excluding `.git`, `.env`, Python bytecode and caches.

The remote command runs `bash deploy/install.sh`. That script generates unique secrets on the target (or preserves an existing `.env`; however, the target-path guard means a new target is expected), validates secrets, checks Compose, builds images, starts the stack, runs `tests/qualification.sh` and `tests/synthetic-e2e.sh`.

A successful workflow uploads:
- source commit SHA and run identity;
- qualification result;
- sanitized Compose service status.

The artifact must never contain `.env`, private keys, tokens, database dumps or raw model prompts.

## What this workflow does not yet automate

- In-place upgrades of an existing AIOps2 installation.
- Database schema upgrades on existing PostgreSQL/MariaDB volumes.
- Consistent backup of PostgreSQL, MariaDB, GLPI documents, Temporal, n8n, Grafana and Prometheus state.
- Restore drills and RPO/RTO proof.
- Automatic application rollback after database migrations.
- Immutable GHCR image publication and digest-based promotion.
- NIM/Nemotron application-level qualification; the deployment's generic qualification does not prove NIM is connected.
- GLPI/OIDC external integration qualification unless those integrations are separately configured and tested.

These are separate release gates. Do not point this first-install workflow at an existing production directory or mount/copy SRV-DEB-05 volumes.

## Acceptance test

Before using the workflow on a customer or development host:
- [ ] Configure protected GitHub Environment and reviewer.
- [ ] Provision a disposable Debian 12 host with a dedicated non-root Docker user.
- [ ] Pre-verify and pin its SSH host key in `DEPLOY_SSH_KNOWN_HOSTS`.
- [ ] Confirm the target directory does not exist.
- [ ] Run workflow with an immutable reviewed SHA.
- [ ] Verify all services and synthetic E2E pass.
- [ ] Inspect the uploaded manifest and service list for secrets.
- [ ] Destroy the disposable host only after retaining required evidence; never delete persistent volumes as an automatic failure handler.

## Current status

The workflow is implemented as a guarded first-install path. It is not yet operationally enabled until the GitHub Environment, reviewers, four SSH secrets and a disposable Debian 12 target are provisioned. No SSH deployment was performed as part of authoring this workflow.
