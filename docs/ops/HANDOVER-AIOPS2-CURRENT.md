# AIOPS2 current handover — 2026-11-11 22:16 Europe/Paris

Scope: differential upgrade audit, not reconstruction. Branch-only handover, coordinate with other concurrent handover Drafts before integration.

- Current increment: S-022 unrecognized `states` key can spoof aggregate READABLE_UNVERIFIED while dashboard/runs/twin are all UNKNOWN. Source blob `ac58f73c725f5e088081bffed4478ea18585ef5c`. Source-derived only; deployed v28/V145 unknown.
- Negative acceptance and before/after matrix: `docs/audits/AIOPS2-STATE-KEY-SPOOFING-S022-20261111.md`. Specified, NOT executed. Candidate fix scoped to validated state keys; ACL tenant/HITL fail closed.
- Previous #655 CI: run 43093715006 SUCCESS at head `8da0c2f01ed0a18e1e17479ee1eaa54245c5cd7c`; not E2E, not evidence for this branch.
- Current Draft: CI must be tied to exact head SHA and classified independently from source and Debian. Host freshness UNKNOWN; E2E NOT VERIFIED.
- #557: operator-confirmed rootless Docker under aiops UID 1001, socket `/run/user/1001/docker.sock`, 87 containers and 210 images at observation; sudo rootful daemon 0 is not data loss. No storage recovery.
- Rollback: close Draft or revert its two documentation commits; no main/merge/deploy/runtime/Docker/cron/secrets/PG/GLPI/other-stack changes.
- Handoff: issue #555; review candidate parity for dashboard, Core/Twin/Runs, NOC, GLPI, Copilot, Evidence, navigation before upgrade.
