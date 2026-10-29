# AIOps2 automated qualification and runtime cron

## What runs automatically

- .github/workflows/quality.yml: existing source, unit, contract and ephemeral-integration gates run on pull requests and pushes, plus daily at 02:23 UTC and on manual dispatch.
- .github/workflows/runtime-smoke.yml: read-only checks of the deployed Debian runtime every 15 minutes, using a repository-scoped self-hosted GitHub Actions runner labelled aiops2-runtime.

The runtime smoke checks verify the four known deployed containers (Core, Worker, Policy, Evidence), their HTTP health endpoints, the Golden Payment synthetic scenario contract, the deployed Worker image and its non-null synthetic observed_at source contract, and TCP connectivity from Worker to Temporal.

The runtime smoke is deliberately read-only. It does not create incidents or Runs, write Evidence, invoke the DEMO endpoint, modify GLPI, restart containers, or perform remediation. A separate approved synthetic E2E test is required to prove a complete workflow.

## Install the self-hosted runner once on SRV-DEB-05

1. In GitHub, open alimtalbi-ata/aiops → Settings → Actions → Runners → New self-hosted runner.
2. Select Linux x64 and follow GitHub's current download and configuration instructions on SRV-DEB-05.
3. Run the runner as the unprivileged aiops account, not root. Configure it for this repository only and add the label aiops2-runtime.
4. Ensure the aiops account can run the required read-only Docker commands. It needs access to docker inspect and docker exec; do not expose the Docker socket to other users.
5. Install and start the runner as a service using the svc.sh commands printed by GitHub.
6. In Settings → Actions → Runners, confirm the runner is Idle/Online and carries the aiops2-runtime label.
7. Use Actions → AIOps2 deployed runtime smoke → Run workflow once. Confirm the log ends with AIOPS2_RUNTIME_SMOKE=PASS.

Do not paste the one-time runner registration token into chat, Git, shell history, or workflow YAML. Do not configure this runner for untrusted pull-request workflows. The workflow intentionally has only schedule and manual-dispatch triggers.

## Cron schedules

GitHub Actions cron uses UTC:
- Runtime smoke: every 15 minutes (*/15 * * * *).
- Full existing quality gates: daily at 02:23 UTC (23 2 * * *).

GitHub scheduled workflows can be delayed during load and run only from the default branch. The runtime schedule does not start until the runner is installed, online, and the PR containing this workflow is merged into main.

## Important source/runtime divergence

The GitHub main Worker source inspected during setup does not match the currently deployed Worker image/source on SRV-DEB-05. The deployed image currently reports aiops2-acme-candidate:worker-observed-at-fixed-20261030; do not rebuild or deploy the GitHub main Worker over it until the corrected deployed implementation has been reconciled into a reviewed branch and tested. The runtime smoke checks the deployed container, not equivalence to GitHub source.

## Evidence boundaries

A green scheduled smoke means only that the listed read-only health and contract checks passed at that time. It does not prove a new Temporal Run, Analyst/Critic/Policy completion, GLPI synchronization, production qualification, or LIVE remediation. The old pilot RUN-2646AF806DC7CB40 remains historical and BLOCKED; this workflow does not mutate or relabel it.
