# Debian cron read-only reporter (account: aiops)

## Design

The existing Debian cron runs a fixed, local Python probe every five minutes as the unprivileged `aiops` account. It never downloads or executes commands from GitHub. It collects CPU load, memory, disk, Docker container state/image names and loopback TCP reachability for PostgreSQL, Temporal, Portal, Grafana and Prometheus. A local lock prevents overlap. Output is bounded and contains no environment variables, container environment, logs, SQL data, GLPI records, user data or credentials.

A local snapshot is refreshed every five minutes. One report is published to `ops/debian-runtime-reports` every 15 minutes to avoid 288 Git commits per day. GitHub is used only as the report sink; no task queue or remote shell exists.

## Prerequisites

- Debian host account `aiops`; do not run as root.
- Python 3 standard library.
- Existing cron daemon.
- A fine-grained GitHub token for `alimtalbi-ata/aiops`, **Contents: read/write only**, no Actions, Administration, Issues, Workflows or Deployments permissions. Store outside the checkout at `/home/aiops/.config/aiops/github-token`, owner `aiops:aiops`, mode `0600`.
- The writable report branch `ops/debian-runtime-reports` must exist.

Never put the token in crontab, shell history, a repository file, a command-line argument or a report.

## Installation (operator executes on SRV-DEB-05)

From a reviewed checkout containing this PR, as account `aiops`:

```bash
install -d -m 700 /home/aiops/.local/bin /home/aiops/.local/state/aiops-debian-agent /home/aiops/.config/aiops
install -m 700 scripts/debian-readonly-reporter.py /home/aiops/.local/bin/aiops-debian-reporter
# Provision the fine-grained token through the host's approved secret manager,
# then ensure: chown aiops:aiops /home/aiops/.config/aiops/github-token
# and chmod 600 /home/aiops/.config/aiops/github-token
python3 /home/aiops/.local/bin/aiops-debian-reporter
```

The first manual run writes a local snapshot. At UTC minutes 00/15/30/45 it also publishes to GitHub. To validate publishing immediately, run at one of those minutes; do not alter the script to force a publish.

Add the following to the `aiops` user's crontab only after reviewing the first local snapshot:

```cron
*/5 * * * * /usr/bin/flock -n /home/aiops/.local/state/aiops-debian-agent/cron.lock /usr/bin/python3 /home/aiops/.local/bin/aiops-debian-reporter >> /home/aiops/.local/state/aiops-debian-agent/cron.log 2>&1
```

## Read and validate

- Local latest: `/home/aiops/.local/state/aiops-debian-agent/latest.json`
- GitHub latest: `ops/debian-reports/SRV-DEB-05/latest.json` on branch `ops/debian-runtime-reports`
- The agent reports observation only. TCP reachability is not application health; Docker health status is only as good as the image healthcheck.
- No service restart, container exec, image pull, migration, GLPI write, Temporal workflow, SSH, sudo or LIVE action is performed.

## Disable / rollback

Remove the single crontab line. Preserve the local report for investigation. Revoke the dedicated token if compromised. Removing the script does not alter running services.
