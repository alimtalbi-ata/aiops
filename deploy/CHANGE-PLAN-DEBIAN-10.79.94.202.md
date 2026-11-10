# Change plan — Debian 10.79.94.202

Status: **DRAFT / NOT AUTHORIZED / NOT EXECUTED**  
Prepared: 2026-11-10  
Target: `10.79.94.202`  
Network constraint: **DNS must not be used**. Use the literal IP only.  
Deployment strategy: isolated side-by-side installation; no in-place upgrade.

## 1. Current decision

**HOLD. Do not connect to or modify the target host until all entry gates below are evidenced and the change is explicitly approved.**

This document is a preparation artifact only. It does not authorize SSH, package installation, firewall changes, container operations, database access, credential rotation, migration, service restart, or cutover.

## 2. Repository facts that affect the plan

The current `main` branch was inspected at `0e232c9fdf4a519de36ba8035b506621854e0277`.

- `deploy/install.sh` runs `deploy/init-env.sh`, `deploy/preflight.sh`, validates Compose, builds images, runs `docker compose up -d`, then qualification and synthetic E2E.
- `deploy/preflight.sh` checks Docker/Compose, disk space, environment secrets, Compose rendering, Dockerfiles and expected ports. It also calls `deploy/init-env.sh`.
- `RETIRE_LEGACY=1` invokes `deploy/retire-legacy.sh`; this must never be set in this change.
- `compose.yml` uses fixed container names such as `aiops2-postgres` and the named volume `aiops2-postgres-data`. Its published host ports (including the Portal mapping) do not explicitly bind to `127.0.0.1` in the inspected main-branch content.
- The default Compose project/service/volume naming and the installer are therefore **not proven isolated from an existing AIOps installation**.

**Consequent HOLD:** do not run `deploy/install.sh` against the target as-is. Before deployment, provide a reviewed isolated Compose overlay or isolated installer that guarantees:
1. unique Compose project name and unique container names;
2. unique, separately backed-up named volumes and database identity;
3. all published host ports bind explicitly to `127.0.0.1`;
4. no DNS lookup, hostname dependency, external ingress or firewall opening;
5. no access to, mount of, or mutation of existing production volumes/containers;
6. no implicit migration or retirement of legacy services.

The earlier proposed ports (Portal 17777, GLPI 18080, n8n 15678) are planning values only; the current main-branch Compose excerpt does not prove that the complete isolated stack is configured with those exact bindings.

## 3. Entry gates — all required

### Security and release
- [ ] P0 issue #535 closed only after non-secret evidence of credential validity assessment/revocation, usage audit, copies/history assessment and independent security approval.
- [ ] Independent review recorded for the release PRs; author self-review is not accepted as independent.
- [ ] All release PR heads rechecked: expected SHA, required checks green, no unresolved review threads, clean mergeability.
- [ ] A single release candidate SHA and immutable image/package digests recorded.
- [ ] No n8n workflow activation; imported example must remain inactive and return static HOLD.

### Target host and isolation
- [ ] Change owner and authorized Debian operator identified.
- [ ] Maintenance window, outage budget, rollback owner and stop conditions approved.
- [ ] Host OS/version, architecture, disk, memory, Docker/Compose versions and existing services inventoried read-only.
- [ ] Existing container names, Compose projects, networks, volumes, mount points, ports and database identities inventoried.
- [ ] Free disk comfortably exceeds image build/pull plus backup and rollback requirements; the current preflight threshold alone is not sufficient evidence.
- [ ] Isolated overlay reviewed to prove loopback-only published ports and unique names/volumes.
- [ ] No DNS, no hostname resolution, no changes to resolver, hosts file, firewall or routing.
- [ ] No credentials copied into GitHub, chat, logs or command-line arguments.

### Backup and restore
- [ ] Consistent database backup created using a client compatible with the actual database major version.
- [ ] Backup checksum, timestamp, size and encrypted storage location recorded without exposing secrets.
- [ ] Restore rehearsed on a separate disposable database/volume.
- [ ] Application data, configuration and n8n/GLPI integration state backed up separately as applicable.
- [ ] Rollback procedure tested and owner named.
- [ ] Existing production volumes remain untouched throughout.

## 4. Proposed execution phases — only after authorization

1. **Read-only discovery:** connect to the literal IP using the authorized access method; collect host and Docker inventory. Do not change state.
2. **Preflight:** verify OS/resources/ports, validate the isolated Compose render, inspect all bind mounts and volume names. Stop on any collision or external bind.
3. **Backup:** capture consistent backups and verify checksums; perform a restore rehearsal away from production.
4. **Stage isolated stack:** deploy only under a unique project namespace with loopback-only bindings and new volumes. No DNS and no public ingress.
5. **Qualification:** health checks, DB migration rehearsal on the isolated DB, Core/Worker/Twin/Portal smoke tests, authentication/tenant isolation, audit logs and DR restore.
6. **Canary:** use only an explicitly approved local operator test. No LIVE workflow, no production write path, no external integrations until separately approved.
7. **Cutover:** separate change approval required. Do not switch ports, routes, firewall, DNS or consumers implicitly.
8. **Observation:** monitor health, logs, resource use, error rates and DB state for the approved observation window.
9. **Closeout:** record deployed SHA/digests, test evidence, backup reference, residual risks and rollback decision.

## 5. Stop / rollback conditions

Stop immediately and do not proceed if:
- any existing container, network, port, volume or database would be reused or modified;
- a port cannot be bound to loopback;
- any step requires DNS or external network exposure;
- a backup cannot be restored successfully;
- a migration is irreversible or has no rehearsed rollback;
- credentials, tenant boundaries or service identities are ambiguous;
- any P0 security HOLD or required review remains open;
- observed host state differs materially from the approved inventory.

Rollback means stopping only the newly created isolated project and restoring its own snapshot/state. Never use `docker compose down -v`, broad prune commands, or deletion of pre-existing volumes. Never run `deploy/retire-legacy.sh` as part of this change.

## 6. Current state

- GitHub CI results are not equivalent to target-host qualification.
- No target-host connection or command has been run.
- No DNS has been used.
- No container, volume, network, credential, database or firewall on the target has been changed.
- No deployment, migration, cutover or rollback has been executed.

**Final authorization required:** explicit approval of the reviewed release SHA, isolated Compose design, backup/restore evidence, maintenance window and named operator before any target-host action.
