# Source-built synthetic POC kit

Not a production release. Use a dedicated rootless Docker daemon, Compose v2 and an operator-owned absolute V3_ROOT. The target default is /srv/aiops-v3; use a separate writable directory for an isolated lab. Never reuse production credentials or data.

From the repository root, after provisioning a dedicated rootless Docker daemon with `data-root` set to an existing canonical strict descendant of `V3_ROOT` (for example `$V3_ROOT/docker-data`). Do not reuse or reconfigure an existing daemon. The launcher checks the explicit current-user socket and daemon storage before writing POC data:

```sh
export V3_ROOT="$HOME/aiops-v3-poc"
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"
unset DOCKER_CONTEXT
bash v3-spike/kit/poc-start.sh
python3 v3-spike/kit/poc-gamma.py
```

Open the loopback URL printed by GAMMA. The launcher builds Core, Twin, Evidence and Policy from source, starts PostgreSQL and seeds a synthetic scenario. GAMMA exposes verified context, evidence, conditional latency preview, deterministic Copilot, simulation and synthetic HITL. Root cause remains UNKNOWN; no host action is authorized.

PostgreSQL data is under V3_ROOT/data/postgres. Generated credentials are stored in V3_ROOT/poc.env; do not publish this file. Docker image/cache storage must remain inside V3_ROOT. The source daemon check is not a full product Compose or OCI qualification. Disposable CI runner provisioning writes daemon/service configuration outside V3_ROOT only for the lifetime of that runner; runtime socket is non-persistent. Services use ephemeral loopback ports.

CI evidence: rootless startup, restart, database backup/restore into a separate synthetic database, and HITL approval/refusal/replay passed in workflow 45690970042 (rootless job 139475994884). These are CI tests, not a complete backup/restore CLI or new-host recovery qualification.

Limitations: source builds use mutable base tags; no immutable product BOM, release provenance, production ACL, real human authentication, or live remediation qualification is claimed. The launcher applies additive migration 008 to the dedicated POC database before starting application services, taking a private pre-upgrade dump when the column or index is missing. Other schema upgrades and full rollback/new-host recovery require separate validation. Do not use this kit against existing hosts or production systems.

### Optional Mattermost lab configuration

Create `$V3_ROOT/mattermost.env` with mode 0600, owned by the POC user, containing `TOKEN=<dedicated slash command token>` and `CHANNEL_ID=<26-character lab channel ID>` on separate lines. Restart the foreground GAMMA launcher. The endpoint is `/api/v1/mattermost/command` on its printed loopback address. Without this file ChatOps is disabled. Never reuse production tokens. Native Mattermost server transport still requires an isolated network design; no public bind is enabled.

## Executable POC lifecycle

Use the new controller on a **fresh, private (0700), dedicated rootless LAB root** whose Docker data directory has already been provisioned and attested. Never point it at an existing production daemon. From the repository root:

```sh
export V3_ROOT="$HOME/aiops-v3-poc"
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"
unset DOCKER_CONTEXT

python3 v3-spike/kit/pocctl.py install
python3 v3-spike/kit/pocctl.py health
python3 v3-spike/kit/pocctl.py gamma
```

Open the loopback GAMMA URL printed by the foreground launcher. The optional `--orchestration` flag on install/start/health includes the Temporal and Worker profile; use it consistently for that profile. Health reports actual container readiness for the selected services, not GAMMA or an end-to-end business qualification.

After stopping foreground GAMMA (Ctrl-C), manage the same installation without rebuilding or reseeding:

```sh
python3 v3-spike/kit/pocctl.py backup
python3 v3-spike/kit/pocctl.py stop
python3 v3-spike/kit/pocctl.py start
python3 v3-spike/kit/pocctl.py health
```

Install refuses an existing data directory or credential file; a partially failed installation requires investigation, never automatic deletion or reinitialization. Start reuses local images only. Stop preserves containers and data. Backup creates a private PostgreSQL custom-format archive under `V3_ROOT/backup`, verifies its catalog with pg_restore --list, and reports SHA-256 and size. This is a logical PostgreSQL snapshot only: it excludes Temporal, collector authority/witness, GAMMA clock and secrets. Catalog validation is not a restore test. Do not copy or restore authority/witness with the application database.

For a separate guarded-collector demonstration, stop any foreground GAMMA first, then provision once:

```sh
python3 v3-spike/kit/pocctl.py provision
python3 v3-spike/kit/pocctl.py gamma --port 18081
```

Choose a free dedicated loopback port and reuse it across restarts. On a provisioned root the controller never silently falls back to the legacy GAMMA launcher. The collector token remains private in `collector-control/collector.token`. Actual target collection and server-owned Verify are separate steps. No automatic rearm, host remediation or production authorization is enabled.

This controller is a source-built POC, not the signed offline OCI release. Full restore, coordinated multistore backup, upgrade and rollback remain separate work; do not treat these commands as an Enterprise disaster recovery procedure.

## Verify a logical backup by isolated restore

On the dedicated source-built LAB daemon, stop foreground GAMMA and other external clients. Use a trusted backup receipt from pocctl.py backup. Supply its archive basename and SHA-256 to poc_restore_check.py:

```sh
python3 v3-spike/kit/poc_restore_check.py "$ARCHIVE_BASENAME" "$BACKUP_SHA256"
```

This restores into a fresh disconnected disposable container, not the active database. The archive must be private, canonical, no larger than 32 MiB and match the supplied digest. PASS means the archive could be restored and the destination schema and rows projected; the standalone check does not attest equality with an independently captured source snapshot. It does not restore Temporal, the collector authority or witness. If resource creation has an ambiguous result, investigate the isolated residue; do not delete unverified resources. The post-E17 CI recipe is separate and checks source/destination hashes, DEMO run identities, Evidence digests and the exact Core execution receipt. Full business stages and coordinated recovery are not qualified by it.
