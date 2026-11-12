# Portal V3 differential qualification — 2026-11-12 03:12 Europe/Paris

## Evidence classes and current gates
CODE: #660 Draft head `21ce7d161d4d29308905f2925e6df92b4612988b`, whitelist unknown keys. #663 Draft head `0db8dd3d43354ec122a6248ebd86d32461814c98`, documentation. #669 Draft head `84b7735bc1e52f9a6af3513ae3d09fd29ef3db96`, presentation module not wired. #670 Draft head `abf05521c55432c8b41699fcd6d5260f9a635fd7`, rootless collector stacked on #665; not a production collector.
CI: #660 Actions 43109660723 completed failure; no S-022 pass attested. Other heads require exact-SHA workflow verification. A green upstream/base SHA does not qualify a candidate.
DEBIAN: UNKNOWN at this timestamp; no authenticated host session. Historical operator rootless evidence UID 1001, socket /run/user/1001/docker.sock, 87 containers / 210 images; observation is not current inventory. No sudo docker.
E2E: NOT VERIFIED. No deploy/cron/install authorized until exact candidate SHA, full CI, compatibility, tested rollback, smoke and independent ACL/HITL review.

## Baseline v28/V145 -> stable -> candidate matrix
UNKNOWN means no reproducible baseline and candidate artifacts have been compared, not absence of functionality.

| Capability | v28/V145 baseline | stable deployed | Portal V3 candidate / required negative |
| --- | --- | --- | --- |
| Dashboard | UNKNOWN | UNKNOWN | #660 extra states must not promote UNKNOWN |
| Incidents | UNKNOWN | UNKNOWN | tenant-scoped list, forged tenant => 403 |
| CMDB / service map | UNKNOWN | UNKNOWN | cross-tenant node/edge => deny |
| NOC | UNKNOWN | UNKNOWN | CI NOC job success is not host health; stale alarm => UNKNOWN |
| Core / Twin / Runs | UNKNOWN | UNKNOWN | malformed Run must not leave partial panels; bounded pagination |
| Evidence | UNKNOWN | UNKNOWN | mismatched run_id/mode/incident_id => reject |
| Policy / HITL | UNKNOWN | UNKNOWN | no implicit LIVE/approve; negative refusal |
| Prometheus / Grafana | UNKNOWN | UNKNOWN | empty/stale history distinct from healthy |
| GLPI | UNKNOWN | UNKNOWN | no write; forbidden ticket => 403 |
| Copilot ticket / portal | UNKNOWN | UNKNOWN | no forged identity or cross-tenant ticket |
| Navigation / auth | UNKNOWN | UNKNOWN | 401/403/404/405, cancellation, supersession, keyboard and CSP |

## Collector #670 review and negative protocol H-024
Source review of #670 identifies *coverage gaps*, not observed host defects: container and image lists are capped at 150 rows (historical 210 images => inventory potentially incomplete); current proposed collector does not enumerate ports, volume metadata, per-container health in structured form, image digests or recent redacted logs. It deliberately marks events/logs/endpoints UNKNOWN. Docker image names and systemd unit names can be sensitive metadata: do not publish raw report.

Execute in an isolated disposable environment against exact #670 head (not production):
1. `python3 -m py_compile scripts/observability/debian_rootless_readonly.py`.
2. Mock UID !=1001: exit 3, no report. Mock socket absent/command failure: section UNKNOWN, never zero containers. Mock held flock: exit 4. Mock slow docker: bounded timeout, UNKNOWN.
3. Mock 210 images: assert inventory reports explicit total and truncation; currently expected **FAIL / GAP** if only first 150 are returned without truncation flag. Never silently claim completeness.
4. Assert 0600 report, 0700 output dir, atomic JSON, 24-file retention, no environment/mount contents/volume payloads/credentials; symlinked output path rejected. Redaction must be tested before adding any logs.
5. Compare host observation timestamps to report collection time and to GitHub commit SHA; UNKNOWN if missing. Do not equate host health with tenant-authorized business READY.

## Host collection and release protocol
After independent review, authenticated `aiops` UID 1001 can run *read-only* `DOCKER_HOST=unix:///run/user/1001/docker.sock docker context show`, `docker ps -a --format '{{json .}}'`, `docker image ls --digests`, `docker volume ls`, `docker info --format '{{json .}}'`, `systemctl --user --no-pager status docker`. Capture only approved metadata and redact before distribution. Do not run `sudo docker`. No authenticated host channel exists in this run, therefore commands NOT EXECUTED.

Only after exact-SHA CI green, verified compatibility, portal-only backup/restore rehearsal and tenant/HITL negative checks: one change per short window, capture before/after, health and smoke checks, immediate portal-only rollback on failure. Never mutate five other stacks, secrets, GLPI/PG, volumes, main or LIVE. Cron collector optional after separate review with flock, timeout, minimal permissions and bounded retention; no periodic upgrades.

## Rollback
Close this Draft or revert its documentation-only commits; no production changes to undo. #557 is rootful/rootless diagnostic error per historical operator evidence, not storage loss. #535 and ACL qualification remain independent release gates.
