# AIOPS2 current handover — 2026-11-12 03:12 Europe/Paris

## CODE
Differential audit H-024: `docs/audits/AIOPS2-PORTAL-V3-HOST-GATES-H024-20261112.md`. #660 S-022 Draft SHA `21ce7d161d4d29308905f2925e6df92b4612988b`; #663 Draft SHA `0db8dd3d43354ec122a6248ebd86d32461814c98`; #669 presentation-only SHA `84b7735bc1e52f9a6af3513ae3d09fd29ef3db96`; #670 collector Draft SHA `abf05521c55432c8b41699fcd6d5260f9a635fd7`. #670 currently caps 150 image rows despite historical 210, without completeness flag; H-024 negative protocol expects failure until addressed.

## CI
#660 run https://github.com/alimtalbi-ata/aiops/actions/runs/43109660723 conclusion failure; S-022 not attested. New Draft CI UNKNOWN until checked at final SHA. Do not infer pass from other branches.

## DEBIAN
NOT INSPECTED. No authenticated access to SRV-DEB-05. Historical rootless UID 1001 / socket /run/user/1001/docker.sock, 87 containers and 210 images, not a fresh measurement. No collector installation, cron, Docker change or deploy. Logs expurgés: NONE collected.

## E2E
NOT VERIFIED. Baseline v28/V145 and stable deployed are UNKNOWN until host snapshots and route-by-route negative checks. ACL/HITL and #535 release holds remain; #557 is a rootful/rootless diagnostic error, not lost storage.

## Rollback
Close Draft or revert only documentation commits. No main merge, service changes or data modifications. Handoff #555; coordinator should verify #670 completeness, exact SHA CI, portal-only backup/rollback and 401/403/404/405 smoke before any host action.
