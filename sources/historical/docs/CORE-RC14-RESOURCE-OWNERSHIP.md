# AIOps 2.0 — RC1.4 isolated deployment resource ownership

**Owner:** Abdelhalim Talbi  
**Target:** `feat/core-analysis-quality-v2`  
**Modes:** development reconstruction / synthetic-only AI qualification; LIVE effects remain disabled.

## Problem fixed

Containers, networks and named volumes in a surviving V1/V2 Docker installation may still exist even when their source Compose trees have disappeared. An install script must never adopt such resources just because a visible name matches.

## Runtime fence

`deploy/install-isolated.sh` first establishes `AIOPS_STACK_ID=aiops2-rebuild`, loopback bindings and a standalone `.env` with restrictive permissions. It runs `deploy/plan_isolation.py` to validate project identity, resolved Compose service/container/network/volume identifiers and host port uniqueness.

Immediately before calling the installer, it sends the resolved Compose JSON model to `deploy/check-docker-ownership.py`. This extra read-only fence calls Docker inspect for each named container, network and volume and checks `com.docker.compose.project`.

- Missing resource: safe to create (provided the deployment plan passes).
- Existing resource owned by `aiops2-rebuild`: eligible for management by that project.
- Existing resource owned by any different project or unlabeled: fail closed.
- Inspect returns malformed JSON or Docker fails unexpectedly: fail closed.

This control does not replace file-based backups, Docker access control, change management or full runtime qualification. There is still a time-of-check/time-of-use race: this protects against accidental collisions in a single-host development environment, not a hostile administrator modifying Docker concurrently.

## One-command operator flow

```bash
# Extract the release into a fresh directory under /home/aiops.
bash deploy/install-isolated.sh
```

The script does not retire, prune, restart or remove V1 containers or volumes. Published dashboards are loopback-only and require an SSH tunnel for access. The deployment first validates the Compose model and ownership fence, then builds and starts the isolated stack, applies migrations, checks container health and performs a synthetic portal end-to-end test.

## Qualification and limits

CI runs `tests/test_docker_ownership.py` to exercise owner mismatch, unlabeled/malformed inspect responses, safe missing resources and same-project resource acceptance. Full image builds, PostgreSQL migrations and a deterministic Temporal Analyst/Critic E2E are separate release gates.

**Not proven by CI:** installation on SRV-DEB-05; host-specific port availability; genuine DGX/local model quality; GLPI application-level setup; native production storage adapters; LIVE remediations. These remain explicit future acceptance milestones.

## Failure guidance

If `OWNERSHIP_FENCE=FAIL`, retain the existing resource and review labels, stack IDs and infrastructure change history. Never use `docker rm -f`, `docker volume rm`, `docker compose down -v` or `docker system prune` to force this deployment to succeed on the existing shared server.
