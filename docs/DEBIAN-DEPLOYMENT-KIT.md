# Debian Deployment Kit — Build, install and qualify

**Author:** Abdelhalim Talbi

## Scope

This kit packages the AIOps 2.0 source, Compose topology, secure environment generator, installation/stop utilities, automated qualification, and architecture/operations documentation. It deliberately excludes .env, local VCS state, database volumes, production exports, and prebuilt images. Images are built by the installer for the target host.

## Build the cumulative kit

Run from a clean clone of the repository on Debian 13 or another Linux build host with Bash, Git, Python 3, tar, zip, and sha256sum:

    bash deploy/package.sh

The script runs the static audit, SQL audit, shell syntax checks and Python compilation before creating the ZIP. It creates a versioned, timestamped ZIP in the parent directory, embeds KIT-MANIFEST.txt and SHA256SUMS, and writes a sidecar ZIP checksum. It never packages a live .env.

## Fresh installation

1. Copy/extract the kit to a dedicated directory, for example /home/aiops.
2. Confirm Docker Engine and Docker Compose v2 are installed and the host has at least 8 GiB free.
3. Run:

       cd /home/aiops
       bash deploy/install.sh

4. The first run creates .env with random secrets and mode 0600. Keep it backed up securely; do not send it in chat or commit it.
5. The installer validates the Compose configuration, builds images, starts services, runs health checks and the deterministic synthetic end-to-end test.
6. If any gate fails, preserve the failing logs and do not declare the kit qualified.

## Existing installation / upgrade

- An existing .env is preserved. It is never silently overwritten or rotated.
- A configuration with known demo credentials fails preflight unless AIOPS_DEMO_MODE=1 is explicitly set. Demo mode is only for isolated disposable environments.
- Do not set RETIRE_LEGACY=1 unless a verified backup, rollback plan, impact window and explicit approval are in place. The normal install does not retire legacy services.
- Do not use docker compose down --volumes on a host with persistent data unless destruction is intended and approved.
- The current CI runtime test uses a disposable runner and deletes its test volumes; it is not an instruction for a production host.

## Operations

| Purpose | Command |
|---|---|
| Validate environment | bash deploy/preflight.sh |
| Start/install and qualify | bash deploy/install.sh |
| Stop stack (preserve volumes) | bash deploy/stop.sh |
| Runtime health and endpoint checks | bash tests/qualification.sh |
| Full synthetic workflow | bash tests/synthetic-e2e.sh |
| Static checks | bash tests/static-audit.sh |
| SQL audit | bash tests/sql-audit.sh |

## Endpoints

- Portal: http://<host>:7777
- GLPI: http://<host>:8080
- n8n: http://<host>:5678
- Prometheus: http://<host>:9090
- Grafana: http://<host>:3000
- Alertmanager: http://<host>:9093
- Temporal gRPC: internal port 7233 only

Do not expose internal services directly to untrusted networks. Put public access behind a hardened reverse proxy, TLS, authentication, and network policy.

## Qualification boundary

A successful static workflow proves syntax/contracts only. A successful isolated runtime workflow proves the tested Compose build/start/readiness and synthetic scenario for that commit. Neither proves production readiness, real DGX integration, real CMDB/RAG evidence, LIVE remediation, or production rollback. LIVE actions remain blocked until their adapters and end-to-end safety paths are independently qualified.

## Recovery

Before any upgrade, capture a verified backup of databases and configuration, record the exact Git commit/kit checksum, and define a tested rollback. The kit does not perform automatic production rollback. Keep secrets separate from the kit archive.
