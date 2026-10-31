# Main-branch quality automation

The canonical AIOps quality workflow runs:

- On pull requests.
- On pushes to `main` and `fix/**`.
- Daily at **02:23 UTC** through GitHub Actions `schedule`.
- On manual `workflow_dispatch`.

The scheduled and manual runs use GitHub-hosted runners and the same source/unit/contract/ephemeral-integration gates as the normal workflow. They do not connect to SRV-DEB-05, access its Docker engine, change containers, run migrations or execute LIVE remediation.

GitHub scheduled workflows run from the default branch and may be delayed by platform load. This is source qualification, not a Debian runtime heartbeat. Host runtime observation remains a separate capability and must use the approved read-only reporter or a separately reviewed restricted runner design.

The duplicate two-hour schedule proposal in PR #189 is intentionally not part of this workflow. The 15-minute self-hosted runtime smoke proposal in PR #188 remains separate and blocked until its use of Docker access is reconciled with the Debian service-operation policy.
