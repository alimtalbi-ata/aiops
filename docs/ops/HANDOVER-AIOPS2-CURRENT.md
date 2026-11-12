# AIOPS2 / Portal V3 — current audit handover
Updated 2026-11-12 (Europe/Paris). F-025 differential gate. See docs/audits/AIOPS2-PORTAL-V3-FRESHNESS-F025-20261112.md.

## CODE
Branch: audit/portal-v3-observation-freshness-f025-20261112; Draft PR pending at handover authoring. Documentation-only F-025 negative freshness/provenance protocol. Existing related Drafts: #670 collector, #673 truncation fail-closed, #671 H-024. No code merge.

## CI
UNKNOWN at this branch head until checks are queried. Earlier #660 CI run 43109660723 reported failed; not a result for this branch. No test F-025 execution claimed.

## DEBIAN
NOT_INSPECTED in this run: no authenticated SRV-DEB-05 access. Operator's historical rootless evidence: aiops UID 1001, socket /run/user/1001/docker.sock, 87 containers and 210 images; age and current state UNKNOWN. Rootful sudo docker is a different daemon; #557 is diagnostic mismatch, not evidence of deleted data. No cron, install, deployment or server changes.

## E2E
NOT_VERIFIED. Portal V3 release gate NO_GO pending same-SHA green CI, v28/V145 parity, host provenance, backup/rollback, ACL/HITL and smoke tests.

## Handoff
Coordinator #555: review F-025 with #670/#673 and #545, assign tests and collector rollout after review only. Keep CODE/CI/DEBIAN/E2E distinct.

## Rollback
Close this Draft PR or revert its documentation commits on its branch. No runtime changes to undo. Never merge main automatically.
