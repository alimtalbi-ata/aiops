# AIOPS2 — current differential audit handover (2026-11-11 15:15 CET)

Branch-only document; coordinate canonical ownership with #555 and Draft #599/#618; do not overwrite concurrent handovers.

- Latest audit: `docs/audits/AIOPS2-RUNS-TRUNCATION-ACCEPTANCE-20261111-1515.md`.
- Source: main `app/portal/portal_bootstrap_client.js`, blob `ac58f73c725f5e088081bffed4478ea18585ef5c`. Up to 100 Runs accepted, only first 15 rendered; potential hidden P0 Run in position 16.
- Negative acceptance: 17 synthetic Runs with P0 in position 16; require visible Run or explicit truncation + tenant-authorized access. 101 Runs, invalid ACL, stale JSON and false LIVE must fail closed. Tests specified, NOT executed.
- Previous #618 head `db564b9a533a393a17646881a182990058e64315`, CI run `43027692903` SUCCESS verified 2026-11-11 15:15 CET. New branch CI pending.
- v28/V145, rollback images, active 7777, candidate 17778, host freshness UNKNOWN; E2E NOT VERIFIED.
- #557 rootful/rootless false diagnostic per operator; do not rebuild or search lost storage.
- Rollback: close Draft or revert branch-only docs; no merge/deploy/host/stacks/ACL/HITL changes.
