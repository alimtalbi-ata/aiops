# ACME demo — offline preparation and deployment gates (2026-10-29)

## Source of truth
Base commit: `321fd5a` on `feat/p0-runtime-consolidated-20261029`.
This preparation branch adds read-only checks only. No Docker deployment, data migration, production modification or runtime qualification has been performed by this branch.

## Intended demo
ACME incident generator → synthetic evidence/logs/metrics → Digital Twin → Analyst → Critic → Policy → remediation proposal → **simulated** remediation with before/after and failure path → ticket/communication → portal/Grafana. Each claim must be linked to one run ID, with explicit synthetic provenance.

## What source inspection establishes
- Simulator `POST /api/launch` only accepts DEMO/REPLAY/STORY, creates an incident and run and requests execution.
- Worker has synthetic SAN observations and Analyst/Critic calls. Its consolidated synthetic Policy input uses `OBSERVE` rather than `EXECUTE`.
- Policy requires independent Critic, fresh evidence, known severity and confidence >= 0.90; it can return `PASS/SIMULATE`. LIVE effects remain disabled.
- Core has validated, hash-bound action **proposals** with preconditions, expected postconditions, risk and rollback; `execution_allowed: false`.
- The portal has read-only simple/complex/chaos/smoke_screen **previews**. This does not establish destructive fault injection or live chaos.
- No qualified remediation effect simulator, before/after reconciliation or GLPI end-to-end proof has been established from this inspection. Do not call a Policy SIMULATE verdict a completed remediation simulation.
- `tests/runtime-e2e.sh` is coupled to a particular Docker Compose environment and its database; do not run it blindly on the already-running Debian stacks.

## Offline source gate
From a clean checkout of this branch:
```bash
python3 tools/acme_offline_source_preflight.py
python3 -m compileall -q app/core app/evidence app/policy app/twin app/worker app/simulator
git diff --check
```
The preflight is deliberately static. Its PASS cannot establish runtime or demo readiness.

## Required staging acceptance before a deployment command
1. Confirm clean Git revision, no tracked secrets, immutable image build inputs and a fresh isolated Compose project name/ports/volumes.
2. Run unit tests in pinned isolated images, then fresh database migration and isolated Temporal E2E. Verify run reaches RESOLVED, Analyst and Critic records exist, Policy returns PASS/SIMULATE and effect receipts count is zero.
3. Demonstrate a real **synthetic remediation simulation** artifact: proposed action, target, preconditions, simulated state before/after, expected postconditions, rollback simulation, failure case and evidence. If absent, mark this feature NOT READY.
4. Check GLPI/n8n ticket linkage and role-specific communication, and portal/Grafana visibility. Do not claim them from healthy container status alone.
5. Verify chaos/smoke scenarios only in isolated synthetic mode; check denial/escalation when Critic fails or evidence is stale.
6. Take backups and document restoration for the target staging environment; never alter existing `aiops2-rebuild-*` volumes without an approved rollback.

## Debian deployment rule
**NO-GO for a direct update of the currently running `aiops2-rebuild-*` stack.** A final deployment command will be issued only after the isolated Compose profile, secrets, image build and acceptance evidence are reviewed. Never run `docker compose down -v`, `docker system prune`, an unreviewed migration, or change the running containers just to prepare a demo.

## Existing safe fallback
`docs/ACME-DEMO-RUNBOOK-V2114.md` documents a read-only ACME presentation at the historical portal and expressly distinguishes historical tests from a new E2E qualification. Recheck its endpoints and avoid claiming real DGX success without fresh evidence.
