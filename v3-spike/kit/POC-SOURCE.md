# Source-built synthetic POC kit

Not a production release. Use a dedicated rootless Docker daemon, Compose v2 and an operator-owned absolute V3_ROOT. The target default is /srv/aiops-v3; use a separate writable directory for an isolated lab. Never reuse production credentials or data.

From the repository root, after provisioning rootless Docker:

```sh
export V3_ROOT="$HOME/aiops-v3-poc"
bash v3-spike/kit/poc-start.sh
python3 v3-spike/kit/poc-gamma.py
```

Open the loopback URL printed by GAMMA. The launcher builds Core, Twin, Evidence and Policy from source, starts PostgreSQL and seeds a synthetic scenario. GAMMA exposes verified context, evidence, conditional latency preview, deterministic Copilot, simulation and synthetic HITL. Root cause remains UNKNOWN; no host action is authorized.

PostgreSQL data is under V3_ROOT/data/postgres. Generated credentials are stored in V3_ROOT/poc.env; do not publish this file. Docker image/cache storage follows the dedicated daemon configuration. Services use ephemeral loopback ports.

CI evidence: rootless startup, restart, database backup/restore into a separate synthetic database, and HITL approval/refusal/replay passed in workflow 45690970042 (rootless job 139475994884). These are CI tests, not a complete backup/restore CLI or new-host recovery qualification.

Limitations: source builds use mutable base tags; no immutable product BOM, release provenance, production ACL, real human authentication, or live remediation qualification is claimed. The launcher applies additive migration 008 to the dedicated POC database before starting application services, taking a private pre-upgrade dump when the column or index is missing. Other schema upgrades and full rollback/new-host recovery require separate validation. Do not use this kit against existing hosts or production systems.

### Optional Mattermost lab configuration

Create `$V3_ROOT/mattermost.env` with mode 0600, owned by the POC user, containing `TOKEN=<dedicated slash command token>` and `CHANNEL_ID=<26-character lab channel ID>` on separate lines. Restart the foreground GAMMA launcher. The endpoint is `/api/v1/mattermost/command` on its printed loopback address. Without this file ChatOps is disabled. Never reuse production tokens. Native Mattermost server transport still requires an isolated network design; no public bind is enabled.
