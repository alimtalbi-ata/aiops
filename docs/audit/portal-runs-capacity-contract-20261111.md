# AIOPS2 — differential Runs capacity and trust recipe (2026-11-11 11:07 CET)

Scope: isolated GitHub-only acceptance recipe; no Debian/Docker or production mutation. Historical v28/V145 and fs1073/fs1051/fs621 are UNKNOWN without version-matched evidence.

## New risk: silent loss of Runs visibility

The previously reviewed current bootstrap client (`app/portal/portal_bootstrap_client.js`, blob `ac58f73c725f5e088081bffed4478ea18585ef5c`) accepts up to 100 Runs and displays at most 15. This can silently hide an important Run at index 16+, even when ACL is qualified. **This is a test hypothesis, not a proven defect**. Confirm sorting, pagination, visible count and indication of hidden entries against the exact candidate source before deciding if behavior is regression.

| Contract | Historical v28/V145 | Current source reviewed | Active :7777 / candidate :17778 | Gate |
|---|---|---|---|---|
| Runs list completeness | UNKNOWN | Up to 100 accepted / 15 displayed | UNKNOWN | P1 count/pagination and discoverability |
| Dashboard/Core/Twin | UNKNOWN | Tenant and server actor qualification | UNKNOWN | P0 no unauthorized reads |
| NOC/GLPI/Copilot | UNKNOWN | Separate route/ACL recipes | UNKNOWN | P0 deny unauthorized mutation |
| Evidence LIVE | UNKNOWN | UNKNOWN / READABLE_UNVERIFIED | UNKNOWN | P0 no false LIVE |
| Navigation | UNKNOWN | Previous anchor integrity recipe | UNKNOWN | P1 route validity |

## Negative / non-regression fixture

1. Generate 17 synthetic Runs (unique ids, descending event times, no tenant secrets); place a synthetic P0 failed Run at index 16. Render a qualified, read-only tenant response. Assert either visible pagination/overflow affordance with accurate total and accessible P0, or an explicitly approved product cap; fail if UI implies all Runs are shown while silently omitting it.
2. Repeat with 101 synthetic Runs. Assert truncation to the documented maximum is explicit, deterministic and does not misstate totals; flag unsupported semantics as UNKNOWN, not PASS.
3. Mix two synthetic tenants in a forged HTTP 200 envelope with `tenant_acl_qualified=false` or non-server-derived actor. Assert zero Runs rendered, no upstream request, and UNKNOWN state.
4. Start requests A and B, clear session while A is pending; resolve B then A. Assert no stale Runs or previous tenant identity appear.
5. For each historical or candidate version, record source commit, image digest, timestamp, actor role, HTTP status, total count, visible count, sort order and next-page behavior. Never treat CI loopback as host E2E.

## Evidence gates

- Current GitHub source blob above is **source-only** and needs refetch at exact candidate SHA.
- Prior Draft #599 head `f5138fc4857cd66b67d558cdd644afb05582274f`: quality-gates run https://github.com/alimtalbi-ata/aiops/actions/runs/42992879047 completed SUCCESS (checked 2026-11-11 11:07 CET). This does not establish execution of this new fixture or Debian E2E.
- This document: acceptance protocol only, no pytest or HTTP execution claimed. Candidate CI: NOT_VERIFIED until exact SHA run is inspected.
- Debian rootless evidence is operator-provided historical context: UID 1001, /run/user/1001/docker.sock, 87 containers, 210 images. #557 is rootful/rootless diagnostic mismatch, not proof of data loss. No further storage recovery.

Rollback: close Draft PR or revert this documentation-only commit on isolated branch. Never merge/deploy or modify main, runtime, Docker, five other stacks, cron, secrets, PG/GLPI or ACL/HITL.

Handoff: #555; authoritative docs/ops/HANDOVER-AIOPS2-CURRENT.md must be coordinated with its owning branch (PR #599 has a branch-local copy); do not overwrite concurrently.
