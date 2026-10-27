# Scheduled engineering continuity journal

Every P0/P1 automation execution must leave a dated GitHub report, including when it finds no code change. The report is created on a dedicated branch with a draft PR; never write directly to `main` or claim success before GitHub confirms the commit.

## Naming

`docs/automation-runs/YYYY-MM-DD-HHMM-<axis>.md` using Europe/Paris local time; include UTC time and the automation ID in the report. Inspect previous logs and open PRs first to avoid duplicating work.

## Required report fields

- **Context:** schedule axis/ID, repository, main SHA, working base and branch, relevant previous PRs.
- **Actions:** inspected paths, actual edits, commits and draft PR URL; separate observation from inference.
- **Decisions:** choices, alternatives, justification, related ADR and owner.
- **Problems:** precise failures, limitations, risks, blocked dependencies and mitigation.
- **Verification:** exact commands, environments, exit codes, CI links and tests explicitly not run. Do not confuse synthetic evidence with production qualification.
- **Development plan:** next P0/P1 tasks, dependencies, acceptance criteria and rollback.
- **Handover:** verified state versus UNKNOWN, safe next action and whether canonical docs need updates.

When architecture, decisions, catalog, qualification or continuity change, update the five canonical documents in the same PR. Preserve earlier history and reconcile overlapping draft PRs before merging. If a GitHub write fails, state the failure explicitly. No automated merge, deployment, or LIVE remediation.
