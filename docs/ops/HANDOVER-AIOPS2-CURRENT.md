# AIOPS2 — differential audit handover (2026-11-11 14:16 CET)

Branch-only handover; path absent on main in earlier checks. Coordinate ownership with #555 and Draft #599 before integration; never overwrite a concurrent handover.

- Audit: `docs/audits/AIOPS2-RUNS-VISIBILITY-20261111-1416.md`.
- Source evidence: `main:app/portal/portal_bootstrap_client.js` blob `ac58f73c725f5e088081bffed4478ea18585ef5c`; up to 100 Runs accepted but only first 15 rendered; pagination/critical Run visibility unverified.
- Negative recipe: 17 Runs with P0 at position 16; require explicit truncation plus authorized access or fail acceptance; 101 Runs rejected; forged ACL and stale JSON remain fail-closed.
- Prior #612 SHA `234800da97da84adc6be65d32569e71f4a7c82d8` CI run `43018460718` SUCCESS, not E2E. New PR CI must be checked at exact head SHA.
- v28/V145, active :7777, candidate :17778, rollback images and host freshness: UNKNOWN; no authenticated HTTP comparison. E2E NOT VERIFIED.
- #557 rootful/rootless mismatch confirmed by operator (aiops UID 1001, rootless Docker, 87 containers/210 images at evidence time). Do not investigate lost storage or rebuild.
- Rollback: close Draft or revert branch-only docs; no merge/deploy/runtime/ACL/HITL/stacks mutation.
