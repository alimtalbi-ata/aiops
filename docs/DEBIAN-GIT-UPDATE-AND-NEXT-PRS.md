# Debian development update via installed Git

This script deliberately **does not deploy** containers or execute database migrations. It checks the repository origin, clean worktree, main branch, and fast-forward relationship, then optionally advances local main. It refuses root and dirty checkouts. Run under the repository's normal Git user.

```bash
cd /path/to/aiops
AIOPS_REPO_DIR="$PWD" bash deploy/debian-git-update.sh --check
AIOPS_REPO_DIR="$PWD" bash deploy/debian-git-update.sh --apply
```

`--check` fetches GitHub origin/main and prints the incoming diff summary. `--apply` requires an explicit operator invocation, records the prior SHA under `~/.local/state/aiops/`, and fast-forwards main. Do not run `git reset --hard` to roll back a running service. Deployment and migrations need separate reviewed, version-aware scripts and backups.

**Not verified on Debian**: the real checkout path, SSH credentials, service manager, compose project ownership and portal exposure. The script defaults to `/opt/aiops`, which is a placeholder; use `AIOPS_REPO_DIR` with the actual path. Never paste production secrets into GitHub Actions logs.

## Next development PR sequence

1. PR #44: validate the NIM/Ollama adapter on GitHub Actions; fix checks; merge only when green.
2. Analyst/Critic: add evidence-grounded inference with schema validation and fail-closed HITL, using the common adapter.
3. Integration CI: start real ephemeral n8n/Grafana/GLPI/Temporal/Core; treat Thruk/Checkmk as blocked until a genuine test service is available.
4. Video: authorized screenshots with source identity, timestamps and real session provenance; generate one MP4 with subtitles and evidence manifest.
5. Debian: review actual Compose deployment, backups, migrations and health probes before enabling a separate `--deploy` workflow.

The authorized development workflow may merge and run non-destructive Actions after green checks. This is not authorization to execute remediation against monitored production infrastructure.
