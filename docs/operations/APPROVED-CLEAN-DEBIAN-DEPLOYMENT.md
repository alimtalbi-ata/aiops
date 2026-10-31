# Automated clean Debian deployment from GitHub Actions

**Status:** Controlled first-install automation; not an in-place upgrade workflow.  
**Workflow:** `.github/workflows/deploy-clean-debian.yml`  
**Target:** A new, empty Debian 12 host.  
**Approval model:** No interactive approval prompt; dispatch is gated by exact-SHA ancestry and two successful exact-head CI workflows.

## Purpose and safety boundary

This workflow transfers a reviewed source snapshot to a Debian 12 host over SSH, runs the repository's canonical `deploy/install.sh`, and collects sanitized deployment evidence.

It is restricted to a dedicated clean installation path under `/home/aiops/aiops2-clean-*`. The remote preflight requires the SSH account to be `aiops`, refuses root, requires Debian 12, and refuses to proceed if AIOps2-prefixed containers, volumes or networks already exist. It is not an in-place upgrade workflow and must not target SRV-DEB-05, which is an existing Debian 13 environment.

The workflow does not delete existing resources. If installation or qualification fails, the target directory, generated host-local `.env`, containers and volumes are retained for diagnosis. An operator must inspect the failure and decide the recovery action.

## Automated source gates

Dispatch requires an exact 40-character commit SHA; movable branch and tag names are refused. Before transferring code, the workflow verifies:

1. The source commit is an ancestor of `main` and is associated with a merged, same-repository pull request targeting `main`; an open feature or qualification branch and direct-push-only commits are refused.
2. The latest `AIOps quality gates` run for that exact SHA completed successfully.
3. The latest `Debian 12 and 13 installation and runtime qualification` run for that exact SHA completed successfully.
4. Both workflow runs originate from this repository and the expected workflow paths.

The check is implemented and unit-tested in `scripts/verify_clean_debian_source.py`; it also requires a merged same-repository PR association for the source commit. The GitHub token used for these checks has read-only Contents and Actions permissions. The SSH private key and known-hosts value remain repository secrets and are never written to the repository or artifact.

## GitHub configuration

Configure these repository-level Actions secrets (Settings → Secrets and variables → Actions):

- `DEPLOY_SSH_HOST`: DNS name or IP of a disposable clean Debian 12 host.
- `DEPLOY_SSH_USER`: must be the non-root Linux account `aiops`.
- `DEPLOY_SSH_PRIVATE_KEY`: private key dedicated to this workflow.
- `DEPLOY_SSH_KNOWN_HOSTS`: pre-verified SSH host-key line(s), obtained out-of-band.

Do not use `ssh-keyscan` in the workflow as a trust-on-first-use substitute. The target must have Docker Engine and Compose v2 already installed, more than 8 GiB free, and a writable `/home/aiops` parent directory.

Never put the private key or host credentials in repository files, workflow inputs, or deployment artifacts.

## Run

From GitHub Actions, dispatch **Automated clean Debian deployment** with:

- `source_sha`: exact commit SHA that has both required CI workflows green and belongs to an approved branch.
- `target_root`: a new path matching `/home/aiops/aiops2-clean-<label>`.

The workflow checks the host is Debian 12, the SSH user is `aiops` and not root, Docker/Compose are usable, no AIOps2-prefixed containers/volumes/networks exist, free space is sufficient and the target path is absent. It then transfers a source archive excluding `.git`, `.env`, Python bytecode and caches.

The remote command runs `bash deploy/install.sh`. That script generates unique secrets on the target, validates secrets, checks Compose, builds images, starts the stack, runs `tests/qualification.sh` and runs the synthetic E2E only when the REAL provider is explicitly configured.

A successful workflow uploads the source commit SHA and run identity, qualification result and sanitized Compose service status. Artifacts must never contain `.env`, private keys, tokens, database dumps or raw model prompts.

## What this workflow does not automate

- In-place upgrades of an existing AIOps2 installation.
- Deployment to the current SRV-DEB-05 Debian 13 stack.
- Database schema upgrades on existing PostgreSQL/MariaDB volumes.
- Consistent backup of PostgreSQL, MariaDB, GLPI documents, Temporal, n8n, Grafana and Prometheus state.
- Restore drills and RPO/RTO proof.
- Automatic application rollback after database migrations.
- Immutable GHCR image publication and digest-based promotion.
- NIM/Nemotron application-level qualification unless the real provider is separately configured and tested.
- GLPI/OIDC external integration qualification unless those integrations are separately configured and tested.

These are separate release gates. Never point this first-install workflow at an existing installation or mount/copy SRV-DEB-05 volumes.

## Acceptance test

Before using the workflow on a customer or development host:

- [ ] Configure the four repository-level Actions secrets.
- [ ] Provision a disposable Debian 12 host with a dedicated `aiops` account.
- [ ] Pre-verify and pin its SSH host key in `DEPLOY_SSH_KNOWN_HOSTS`.
- [ ] Confirm the host has no AIOps2-prefixed containers, volumes or networks.
- [ ] Run workflow with an exact immutable SHA and verify both exact-head CI gates.
- [ ] Verify all services and synthetic E2E pass where the REAL provider is configured.
- [ ] Inspect the uploaded manifest and service list for secrets.
- [ ] Retain evidence; never delete persistent volumes as an automatic failure handler.

## Current status

The workflow is an automated, CI-gated first-install path. It still requires the four repository-level SSH secrets and a disposable Debian 12 target. No SSH deployment is performed by CI qualification, and no deployment to SRV-DEB-05 is authorized by this workflow.
