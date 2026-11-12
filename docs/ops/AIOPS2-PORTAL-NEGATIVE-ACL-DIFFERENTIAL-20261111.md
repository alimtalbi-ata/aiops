# AIOPS2 portal — differential negative acceptance: authenticated viewer without tenant ACL (2026-11-11)

Scope: **source/CI-only acceptance protocol**, not an assertion about Debian, the candidate at :17778, or E2E. Baseline inspected: `app/portal/main.py` on `main`, blob `16d156c912ccc7592383f7d67a6a6a36fef50629`. Compare with v28/V145 and fs1073/fs1051/fs621 only after obtaining immutable source/image provenance and time-stamped HTTP receipts. Never treat a Docker rootful inventory as rootless inventory.

## Negative test: viewer token is not tenant/actor authorization

Precondition: isolated test environment, mocked Core/Twin/Copilot upstreams, a *test-only* authenticated viewer credential, **no qualified server-derived tenant/actor ACL**, and no production secret or data. Do not call live endpoints to perform this test.

| Route | Before (source main, expected contract) | After (candidate acceptance) | Negative assertion | Evidence required | Priority / restoration |
| --- | --- | --- | --- | --- | --- |
| GET /api/portal/bootstrap | 503 UNKNOWN, TENANT_ACL_NOT_QUALIFIED | UNKNOWN pending candidate receipt | no dashboard, Core/Twin/Runs payload; upstream call count = 0 | source SHA + test output + actor class | P0: preserve fail-closed; only restore authorized tenant-scoped read contract |
| GET /api/portal/components | 503 UNKNOWN, TENANT_ACL_NOT_QUALIFIED | UNKNOWN | no operator-configured navigation URLs, GLPI/NOC leakage; registry read count = 0 | source SHA + test output | P0: ACL first, then authorized navigation |
| POST /api/copilot | 503 UNKNOWN, TENANT_ACL_NOT_QUALIFIED | UNKNOWN | no forwarding question, body or actor claim; upstream call count = 0 | source SHA + test output | P0: tenant/run scoped server-side authorization |
| POST /api/demo | 503 UNKNOWN after operator authentication without qualified ACL | UNKNOWN | no mutation, no live remediation; upstream call count = 0 | source SHA + test output | P0: HITL/actor/tenant/run gates |
| Navigation fragments Runs/Twin/Copilot/NOC/integrations | Source-only links/anchors tested in #567 | UNKNOWN | reject missing/duplicate targets; do not convert disabled capabilities into enabled links | DOM test + screenshot authorized | P1: restore anchor contract, not privileged APIs |
| Evidence, GLPI, NOC, visualisation UX | route/component presence not equivalent to working contract | UNKNOWN | reject fabricated provenance, stale data labelled fresh, empty chart without state | source + authenticated HTTP + E2E receipt | P1: isolated display correction only |

## Executable acceptance outline (isolated pytest / TestClient)

1. Patch `_require_portal_read_auth` to accept a dummy viewer token only. Patch network helpers and read models to raise immediately on access. For demo, patch `require_demo_operator` to authenticate a dummy operator, **without** granting tenant ACL.
2. Invoke each route using FastAPI TestClient, with fake credentials. Assert HTTP 503, JSON `state == 'UNKNOWN'`, `reason == 'TENANT_ACL_NOT_QUALIFIED'`, no upstream calls, no secret/URL/data leakage. Check `Cache-Control: no-store` and `X-Content-Type-Options: nosniff`.
3. Negative controls: missing/invalid viewer auth must not return protected content. Malformed Copilot JSON must not bypass authorization or be forwarded. Do not change the authorization decision to satisfy a visual test.
4. Repeat on immutable candidate source SHA and historical snapshots **only after** mapping equivalent routes and verifying source provenance; classify missing/renamed routes separately from ACL-denied routes.
5. For live acceptance, obtain independently approved, read-only tenant-qualified identity and fresh, time-stamped receipts for active :7777 and candidate :17778. Do not run this negative test against production with privileged credentials.

## Provenance and evidence ledger

- **GitHub source**: `main` portal blob above; code behavior is a contract claim, not observed host behavior.
- **GitHub CI**: record workflow URL, conclusion and exact head SHA; a green workflow does not prove this protocol's cases ran.
- **Debian rootless**: operator-supplied evidence for aiops UID 1001, rootless socket `/run/user/1001/docker.sock`, 87 containers and 210 images. Direct access in this audit: **DEBIAN UNKNOWN**. Incident #557: rootful/rootless diagnostic mismatch, not evidence of lost storage.
- **Runtime/E2E**: active image `a1f3adcf1e11` is a historical reported observation, not a fresh attestation. Candidate :17778, fs1073/fs1051/fs621, v28/V145 contracts and E2E **UNKNOWN** until immutable mappings and fresh receipts exist.
- **Probable cause if viewer-only response becomes 200**: authorization regression or accidentally bypassed guard; if a link vanishes but API remains ACL-denied, investigate navigation/DOM separately rather than disabling ACL.

## Handoff / rollback

Coordinator: issue #555. Canonical handover is on branch `docs/debian-deployment-qualification-plan-20261110` at `docs/ops/HANDOVER-AIOPS2-CURRENT.md`; do not overwrite it concurrently. Attach PR/head SHA and CI after verification. Rollback of this documentation-only increment: close the Draft PR or revert its single documentation commit **on the isolated branch only**. No Docker/runtime/stack changes, no merge or deployment.
