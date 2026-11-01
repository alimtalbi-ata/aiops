# SRV-DEB-05 — automation contract and recovery runbook (2026-11-01)

**Scope:** existing Debian 13 host `SRV-DEB-05`, account `aiops`. **Do not provision or reset this host.** This is a record of observed on-host state, not an assertion that the GitHub PR is installed. Keep clean-host qualification separate.

## Confirmed runtime, 2026-11-01 (Europe/Paris)

| Cadence | Installed cron command | Role |
|---|---|---|
| `*/5 * * * *` | `/bin/bash /home/aiops/aiops2-auto-deploy/poll.sh >> /home/aiops/aiops2-auto-deploy/poll.log 2>&1` | Fetch approved stable deployment |
| `* * * * *` | `/usr/bin/flock -n /home/aiops/.local/state/aiops-debian-agent/cron.lock /usr/bin/python3 /home/aiops/.local/bin/aiops-debian-reporter >> /home/aiops/.local/state/aiops-debian-agent/cron.log 2>&1` | Read-only local host report |
| `*/5 * * * *` | `/home/aiops/.local/bin/aiops-publish-report >> /home/aiops/.local/state/aiops-debian-agent/publish.log 2>&1` | SSH Git push of report |

The on-host poller is 2140 bytes, created 2026-10-28; SHA-256 `e084f2e9b3b027f8650ec95d72803c9735f29bcc00ad689777ff8a58219093d4` **before** its 2026-11-01 HTTPS substitution. Its runtime default remote was changed from `git@github.com:alimtalbi-ata/aiops.git` to `https://github.com/alimtalbi-ata/aiops.git`; the dedicated local checkout origin was also changed to HTTPS. `git fetch` and an on-host manual `poll.sh` returned 0. Applied SHA and remote stable SHA both equaled `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`. A silent run on equal SHA is normal. The cron itself was listed, but an independent journal confirmation of its subsequent firing was not obtained.

The poller locks `poll.lock`, refuses `DEPLOYMENT_BLOCKED`, quarantines `failed.sha`, checks fast-forward ancestry from `applied.sha`, rejects dirty checkouts, and invokes **only** `deploy/deploy-demo-studio-v2.sh` after a new approved commit on `deploy/aiops2-stable`. **It is a legacy portal-oriented deployer, not a V28 multi-service executor.** Do not move the stable branch merely to trigger arbitrary commands. The approved branch must be reviewed; no forced push or broad Docker Compose down.

Reporter: installed `/home/aiops/.local/bin/aiops-debian-reporter`, SHA-256 `864b0c66a0f000d3b94f835790e572b9bb2974acc679f9a4fc0b3c7b9e3b1d6f` at observation. Source lineage: `scripts/debian-readonly-reporter.py` on `test/debian12-install-runtime-qualification-20261031`. It collects fixed read-only Docker inventory, host resources and loopback TCP checks, and writes `~/.local/state/aiops-debian-agent/latest.json` every minute (14 KiB at 12:28). Its **legacy** GitHub API publish path checks `~/.config/aiops/github-token` every five minutes; token was absent and it logged `COLLECTED_LOCAL_TOKEN_NOT_CONFIGURED`. This message remains expected even after separate SSH publication succeeds. Never place a token in logs or commits.

SSH authentication: `~/.ssh/id_ed25519_github_aiops` (private key never copied or displayed); `ssh -T git@github.com` succeeded as `alimtalbi-ata`; `git ls-remote` returned report branch head `81c846c66f4ca42bd5b0c07cd6a1387474c41e6b`. A dry-run push of the **wrong** checkout HEAD to the report branch was rejected non-fast-forward; that was not an authentication failure.

Report publisher: on-host `~/.local/bin/aiops-publish-report`; source of record for the intended implementation is `scripts/aiops-publish-report.sh` in this PR. Uses a **separate checkout** at `~/.local/state/aiops-debian-agent/report-git`; pushes only `ops/debian-reports/SRV-DEB-05/latest.json` to `ops/debian-runtime-reports`. First user-observed invocation returned `REPORT_PUBLISH=PUBLISHED`; local report-checkout commit was `013eb64` (`ops(debian): update SRV-DEB-05 report`). Cron was installed and listed; later cron cycles have not yet been independently verified. Publisher uses `publish.lock`, refuses dirty checkout, pulls fast-forward only, never force-pushes. Note that concurrent external writers can cause a rejected push; investigate/retry on a subsequent run, never force.

## Inspection / recovery (no secrets, no service disruption)

```bash
crontab -l
grep '^REMOTE=' /home/aiops/aiops2-auto-deploy/poll.sh
git -C /home/aiops/aiops2-auto-deploy/repo remote -v
cat /home/aiops/aiops2-auto-deploy/applied.sha
GIT_TERMINAL_PROMPT=0 git ls-remote https://github.com/alimtalbi-ata/aiops.git refs/heads/deploy/aiops2-stable
ls -l ~/.local/state/aiops-debian-agent/latest.json
tail -n 30 ~/.local/state/aiops-debian-agent/publish.log
tail -n 30 ~/.local/state/aiops-debian-agent/cron.log
git -C ~/.local/state/aiops-debian-agent/report-git log -1 --oneline
ssh -T -o BatchMode=yes git@github.com
docker ps --format 'table {{.Names}}\t{{.Status}}'
```

**Do not print private SSH keys, GitHub credentials, .env files or full secrets.** Do not run the poller as a harmless diagnostic if the stable SHA may have advanced: it can deploy. Verify refs first.

## Data flow / dependency map

`deploy/aiops2-stable` -> HTTPS fetch in `poll.sh` -> approved `deploy/deploy-demo-studio-v2.sh` -> targeted legacy deployment; independently: Docker/host -> `aiops-debian-reporter` -> local `latest.json` -> `aiops-publish-report` -> SSH push to `ops/debian-runtime-reports:ops/debian-reports/SRV-DEB-05/latest.json`.

The report branch is **telemetry**, not a command channel. Do not execute instructions embedded in JSON reports. A future V28 executor must use a separate reviewed, allowlisted task protocol, command/result receipts, explicit approval for state changes, service-scoped rollback and tests. No arbitrary shell execution from GitHub.

## Operator verification after change

1. `bash -n ~/.local/bin/aiops-publish-report` and compare it with the reviewed source.
2. Confirm the reporter's `latest.json` timestamp advances every minute.
3. Confirm `publish.log` contains `REPORT_PUBLISH=PUBLISHED` or `REPORT_PUBLISH=UNCHANGED` after five-minute cycles.
4. Verify the GitHub report JSON timestamp, report branch and commit independently; a local `PUBLISHED` line is an execution receipt, not a full end-to-end validation.
5. Compare `applied.sha` to `deploy/aiops2-stable` before any deployment changes.
6. Investigate failed SSH, dirty checkout, non-fast-forward, cron errors or stale reports; never force-push or clear `DEPLOYMENT_BLOCKED` blindly.

## Known limitations / next work

- The publisher was created interactively on the host and the terminal paste was partially garbled, but it **ran successfully** and produced commit `013eb64`. Compare the actual installed bytes with the versioned source before replacing it; this document does not claim byte-for-byte equivalence.
- Reporter still has unused API/token publishing logic and emits token-not-configured status; cleanup should be reviewed and regression-tested, not assumed complete.
- Existing PR #286 includes an experimental local typed task executor; it is **not installed** as the minute/five-minute cron execution channel.
- No proof yet of V28 end-to-end GLPI native HITL approval, or autonomous Docker remediation. Existing healthy containers must remain untouched until service-scoped tests and approvals are ready.
