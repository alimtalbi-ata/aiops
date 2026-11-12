# AIOPS2 / Portal V3 — handover 2026-11-12 05:16 Europe/Paris

## CODE
F-026 negative release gate and matrix: docs/audits/AIOPS2-PORTAL-V3-NEGATIVE-F026-20261112.md. Draft branch audit/portal-v3-freshness-negative-f026-20261112. Parent F-025 #674 SHA 9844511d0f9560c14aece7d6261dbca0e8b35cbe. Related #670/#673/#676 collector and #669/#672/#675 UX remain independent stacks of Drafts. No merge.

## CI
F-025 exact SHA 9844511d0f9560c14aece7d6261dbca0e8b35cbe: workflow 43146450475 completed SUCCESS (GitHub Actions). This verifies that workflow only, not F-025 fixture execution. F-026 new SHA CI pending/UNKNOWN until queried. Tests F-026 NOT_EXECUTED.

## DEBIAN
NOT_INSPECTED. No authenticated SRV-DEB-05 session available. Historical operator rootless UID 1001 socket /run/user/1001/docker.sock, 87 containers and 210 images are stale, not current health. #557 rootful/rootless diagnostic confusion, not data loss. No install, cron, Docker or deployment performed. Collector #676 has additional count equality safeguards; pending privacy review and test.

## E2E
NOT_VERIFIED. Release NO_GO until same-SHA green CI, fresh rootless host observation, v28/V145 parity, rollback tested and tenant ACL/HITL smoke. No LIVE.

## Coordinator / rollback
Handoff #555; distinguish CODE, CI, DEBIAN, E2E. Git rollback: close Draft or revert docs-only commit(s). No runtime rollback needed. Preserve five other stacks; never merge main automatically.
