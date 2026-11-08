# AIOps2 installation and capability registry

## Purpose

This directory is the Git-tracked reference for what is installed on each AIOps2 host, which capabilities each installed component provides, how components depend on one another, and what has actually been qualified.

GitHub is the durable documentation and change-history repository. It is **not** a live inventory agent: runtime state must be refreshed from the host and timestamped. Never present an old snapshot as current state.

## Sources of truth by question

| Question | Authoritative record |
|---|---|
| What is intended to exist and why? | Architecture, ADRs and component catalog in this repository |
| What was observed on a host at a given time? | Timestamped host inventory under this directory |
| Which exact source/config produced a runtime? | Git commit, Compose file paths and SHA-256 hashes, image tag and image digest |
| What does a component do? | Component catalog plus implementation/API contract and tests |
| Does it work? | Exact-SHA CI, integration/E2E evidence and runtime qualification artifacts |
| Is it safe to retire? | Approved consolidation decision with dependency, data/volume, backup and rollback evidence |

## Required inventory record

Every host snapshot should record:

- host identifier, OS/version, capture timestamp and operator/process;
- Docker Engine and Compose versions;
- Compose project, working directory, exact Compose file list and SHA-256 per file;
- every container: name, ID, state, health status, image reference and immutable image digest;
- Compose project/service labels, restart policy, published ports and networks;
- mounts and named volumes, read/write mode, volume owner and backup status;
- component capability, functional owner, API/queue/database dependencies and security boundary;
- source repository, branch, commit SHA, build workflow/run and artifact provenance;
- qualification state: unverified, source-reviewed, CI-passed, integration-passed, runtime-verified, or approved;
- known drift, exceptions, rollback target and next review date.

## Capability catalog expectations

For every service, document its purpose, inputs/outputs, API or event contracts, state ownership, dependencies, ports, persistent data, authentication, network zone, health signal, tests and operational owner.

Use the existing [component catalog](../COMPONENT-CATALOG-AND-REUSE.md) as the conceptual baseline. Do not create duplicate Core, Run stores, Evidence repositories, orchestration engines, GLPI clients, Portal shells or monitoring stacks without an ADR and measured need.

## Status vocabulary

- **Observed-running**: Docker reported the container running at the capture timestamp. This does not prove the application is ready.
- **Observed-exited / observed-created**: Docker state at capture timestamp.
- **Health-healthy / health-unhealthy**: Docker health-check result, only where a health check is configured.
- **Health-not-configured**: no Docker health result is available.
- **Source-reviewed**: source and contracts inspected.
- **CI-qualified**: relevant checks passed on the exact recorded commit.
- **Runtime-qualified**: behavior tested on the named host with dated evidence.
- **Approved-for-consolidation**: explicit decision after dependency/data/rollback review.

Never collapse these states into a generic "installed/OK" flag.

## Update workflow

1. Capture a read-only host inventory.
2. Sanitize it; exclude all secrets, environment values, credentials, tokens, private keys and customer data.
3. Compare runtime metadata with Git-tracked Compose and source.
4. Update the host snapshot and the component/dependency records in the same PR.
5. Link exact commit, CI runs, test evidence and deployment evidence.
6. Record drift explicitly; do not silently rewrite intended architecture to match accidental runtime state.
7. Review retirement candidates only after functional equivalence, data migration, backup and rollback are proven.

## Current host

See [SRV-DEB-05 inventory snapshot — 2026-11-08](SRV-DEB-05-INVENTORY-2026-11-08.md).

The snapshot currently reports 78 containers (59 running, 18 exited, 1 created), five Compose projects, 18 networks and 59 volumes. These are historical observations from 2026-11-08 and must be refreshed before operational decisions.
