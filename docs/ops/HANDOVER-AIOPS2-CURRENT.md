# AIOPS2 — current differential handover (Draft branch only)
Updated: 2026-11-11 21:07 Europe/Paris.

Scope: functional upgrade differential, not reconstruction. Source evidence: `app/portal/portal_bootstrap_client.js` blob `ac58f73c725f5e088081bffed4478ea18585ef5c` on main. Candidate X-021 acceptance in `docs/audits/AIOPS2-CROSS-PANEL-ATOMICITY-X021-20261111.md`. Cross-panel partial DOM mutation on malformed Runs is a **source-level risk**, not an observed runtime regression. X-021 is **specified, not executed**.

Previous Draft #650 at SHA `3d8b5d18c041b2f0432fe1db1ff4425ab06f4586`: CI Actions run `43084511146` **success**. This does not prove E2E or production parity. CI for this branch must be checked at its exact final head SHA after opening Draft PR.

Functional baseline: Runs 100 admitted/15 displayed; dashboard, Core/Twin and Runs must fail closed under unqualified tenant/actor; NOC/Evidence LIVE requires independent provenance; GLPI and Copilot retain ACL/HITL; navigation parity, v28/V145 and Debian active/candidate remain UNKNOWN without authenticated comparison. No upgrade approval until tests run.

#555 handoff: link PR and final SHA, CI status, X-021 evidence and rollback. #557: operator confirmed aiops UID 1001 rootless Docker socket `/run/user/1001/docker.sock`, 87 containers and 210 images; `sudo docker` queried a different rootful daemon. Do not search for lost storage or rebuild. Historical host evidence only; no new Debian access. E2E NON VERIFIED.

Rollback: close Draft PR or revert its branch-local documentation commits. Never merge, deploy, modify main, Debian, Docker, cron, secrets, PG/GLPI, five other stacks or bypass ACL/HITL.
