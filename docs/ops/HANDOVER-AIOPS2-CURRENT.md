# AIOPS2 / Portal V3 — handover 2026-11-12 07:09 Europe/Paris

## CODE
F-028 on audit/portal-v3-evidence-envelope-f028-20261112, stacked on #680 SHA 3c5ab56b32fcd0c47a57be0f410d126d2adff4c9. Hardened standalone synthetic release evidence gate: explicit CI conclusion SUCCESS, strict 40-lowercase-hex SHA, aware evaluation clock, explicit complete:true inventory. Four new negative methods (missing/failed CI, absent completeness, naive now, invalid SHA). Test file: tests/observability/test_portal_v3_freshness_f027.py. Run: python3 tests/observability/test_portal_v3_freshness_f027.py -v. This is NOT wired into production release controls. v28/V145 -> stable -> V3: dashboard/incidents, CMDB/service map, NOC, Core/Twin/Runs, Evidence, Policy/HITL, Prometheus/Grafana, GLPI, Copilot ticket/portal, navigation/auth: all parity UNKNOWN, needs baseline fixtures and authenticated smoke.

## CI
#680 head 3c5ab56b32fcd0c47a57be0f410d126d2adff4c9: run 43159716613 completed SUCCESS (workflow only; no proof standalone tests executed). F-028 new SHA CI UNKNOWN pending check. No claim of green until exact SHA verified and tests identified.

## DEBIAN
NOT_INSPECTED: no authenticated SRV-DEB-05 access available. Rootless UID 1001, context rootless, socket /run/user/1001/docker.sock; historical 87 containers and 210 images not fresh. Collector drafts #670/#673/#676/#679/#682 require privacy and lock/symlink review; no installation, cron, deployment or host mutations. #557 rootful/rootless false diagnostic, no recovery.

## E2E
NOT_VERIFIED. NO_GO deployment until exact SHA green CI, rootless fresh inventory, baseline parity, compatibility, backups/rollback tested, tenant ACL/HITL smoke and portal-only bounded window. No LIVE, no GLPI writes.

## Rollback
Close F-028 Draft or revert its test+handover commits. No runtime rollback. No merge main or changes to other stacks.
