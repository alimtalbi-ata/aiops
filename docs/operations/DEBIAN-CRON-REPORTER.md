# Debian cron agent and service-operations policy (account: aiops)

## Design

The existing Debian cron runs a fixed, local Python probe every five minutes as the unprivileged `aiops` account. It never downloads or executes commands from GitHub. It collects CPU load, memory, disk, Docker container state/image names and loopback TCP reachability for PostgreSQL, Temporal, Portal, Grafana and Prometheus. A local lock prevents overlap. Output is bounded and contains no environment variables, container environment, logs, SQL data, GLPI records, user data or credentials.

A local snapshot is refreshed every minute. One report is published to `ops/debian-runtime-reports` every 5 minutes to avoid 1,440 Git commits per day. GitHub is currently used only as the report sink. The reporter remains read-only. Authorized application operations are specified separately in `config/ops/debian-service-operations-policy.yml` and `docs/operations/DEBIAN-SERVICE-OPERATIONS-POLICY.md`; they are not yet executable by this reporter.

## Prerequisites

- Debian host account `aiops`; do not run as root.
- Python 3 standard library.
- Existing cron daemon.
- A fine-grained GitHub token for `alimtalbi-ata/aiops`, **Contents: read/write only**, no Actions, Administration, Issues, Workflows or Deployments permissions. Store outside the checkout at `/home/aiops/.config/aiops/github-token`, owner `aiops:aiops`, mode `0600`.
- The writable report branch `ops/debian-runtime-reports` must exist.

Never put the token in crontab, shell history, a repository file, a command-line argument or a report.

## Installation (operator executes on SRV-DEB-05)

From any directory on SRV-DEB-05, as account `aiops`, bootstrap the installer pinned to a reviewed commit (the script downloads the reporter from the PR branch):

```bash
curl --fail --silent --show-error --location https://raw.githubusercontent.com/alimtalbi-ata/aiops/aa3e7cb9c9eb531c831a2d85c4133834a95538a9/scripts/install-debian-reporter.sh | bash
```

The installer downloads and validates the reporter, installs it under `~/.local/bin`, and adds a single `* * * * *` entry to the **aiops user crontab**. It does not require a GitHub token for local collection. To enable publication, provision a fine-grained token at `~/.config/aiops/github-token` with mode `0600` and Contents read/write on this repository.

Manual installation alternative, from a reviewed checkout containing this PR:

```bash
install -d -m 700 /home/aiops/.local/bin /home/aiops/.local/state/aiops-debian-agent /home/aiops/.config/aiops
install -m 700 scripts/debian-readonly-reporter.py /home/aiops/.local/bin/aiops-debian-reporter
# Provision the fine-grained token through the host's approved secret manager,
# then ensure: chown aiops:aiops /home/aiops/.config/aiops/github-token
# and chmod 600 /home/aiops/.config/aiops/github-token
python3 /home/aiops/.local/bin/aiops-debian-reporter
```

The first manual run writes a local snapshot. Cron collects every minute. At UTC minutes 00/05/10/15/20/25/30/35/40/45/50/55 it publishes to GitHub if the token is configured; otherwise it continues local collection and reports `TOKEN_NOT_CONFIGURED`.

The installer adds the following to the `aiops` user's crontab (or add it manually if preferred):

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
