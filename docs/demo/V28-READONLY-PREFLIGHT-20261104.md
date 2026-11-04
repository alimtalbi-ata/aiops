# V28 demo preflight — existing delivery only

This change adds a read-only diagnostic payload for the **existing** Debian delivery mechanism. It does **not** install a cron job, edit the crontab, start/stop containers, deploy images, write GLPI, or authorize LIVE actions.

## Host-side invocation (only by the already qualified delivery job)

```sh
python3 scripts/demo_v28_readonly_preflight.py --output /home/aiops/aiops2-demo-auto
```

Artifacts: `preflight.json` and `preflight.txt`. Exit 0 means the demo is at most `GO_DEGRADE`; exit 2 means `NO_GO`. The script deliberately cannot issue a full `GO`: neither an authenticated STOP_AUTO check nor an actual Temporal workflow or GLPI actor/tenant ACL is established by these probes.

## Integration gate

Before allowing the existing cron consumer to run this payload, verify its **actual** repository/branch selector, job format, signature/hash policy, execution user, allowlist, logging and receipt protocol against the live host configuration. The repo's 2026-10-31 control-plane inventory explicitly recorded the Debian scheduler contract as **UNATTESTED**. Do not invent a second scheduler or assume a PR is deployed.

This PR is **source delivery only** until the existing host-side mechanism is attested and an execution receipt (source SHA, exit code, timestamp, report hash) is returned. Do not merge or auto-execute based on a CI green alone.

## Demo use

Demonstrate a labelled synthetic ACME incident through Core, Twin, Evidence, Policy and Grafana. Show GLPI as a service only; no authorized ticket/Run link is claimed. Keep `STOP_AUTO` enabled. Do not make production mutations for the demo.
