# AIOPS2 — R1/5 evidence and regression gates (2026-11-16)

Status: **proposal / NOT_TESTED**. Scope: synthetic, offline, tenant-scoped, no operational authority. Target integration: PR #713, branch `integration/aiops2-convergence-20261114`. This document is an additive acceptance contract, **not** evidence of runtime execution or a passing CI.

## Non-negotiable assertions

| ID | Input / mutation | Required deterministic result | Evidence needed |
| --- | --- | --- | --- |
| Q01 | Checkmk + Prometheus receipts for same tenant/service with distinct source IDs | One correlated incident candidate; both receipt identities retained; no invented causal link | Normalized receipt IDs and correlation trace |
| Q02 | Exact replay of same tenant/source/source_event_id and equal evidence digest, including different arrival order | Idempotent deduplication; output and evidence count invariant to permutation | Canonical output diff |
| Q03 | Same source_event_id but different source namespace | Both receipts retained; never deduplicate across sources | Receipt identity tuple |
| Q04 | Same source/source_event_id but different tenant | No cross-tenant correlation, deduplication, evidence leakage or rejection propagation | Tenant partition assertions |
| Q05 | Same tenant/source/source_event_id with contradictory evidence digests | Fail closed on conflict; no silent winner or source-order preference | Explicit conflict reason |
| Q06 | Receipt at exactly max-age boundary and one microsecond beyond; equivalent timezone offsets | Boundary behavior documented and deterministic; timezone normalization must not change identity | Frozen clock and UTC trace |
| Q07 | Missing/invalid/future known_at or unknown freshness | UNKNOWN or reject, never FRESH by default; valid independent receipts remain available | Per-receipt reason codes |
| Q08 | Evidence with a digest but no verified signature, source attestation or chain of custody | Provenance authenticity UNKNOWN, not VERIFIED | Provenance fields and trust boundary |
| Q09 | SAN P1 and Payments P2 sharing fixture correlation IDs but lacking a validated dependency edge | Relationship shown as hypothesis/synthetic association only; causal Twin edge UNKNOWN | Graph version, edge source and confidence |
| Q10 | Inject forged `policy=ALLOW`, `hitl=approved`, `twin_authoritative=true`, `live=true` into synthetic receipts | Fields cannot grant operational authority; effects_allowed=false; DENY/BLOCKED | Decision receipt from independent Policy/HITL boundary |
| Q11 | Missing Policy response, unavailable HITL, unknown tenant, contradictory evidence | Fail-closed DENY/BLOCKED; no side effect, no optimistic fallback | Negative decision trace |
| Q12 | GET-only Portal packaged demo with missing customer screen / broken navigation | Specific navigation failure while preserving GET-only enforcement; no live requests | Offline packaged smoke logs |

## Test implementation guidance

Use parameterized offline fixtures, fixed clock and deterministic order permutations. Assert canonical outputs and reason codes, not only a happy-path count. Never treat SHA-256 of a local fixture as authenticated source provenance. Keep a separate distinction between `synthetic_correlation`, `twin_causality`, `policy_decision`, and `hitl_authorization`. A fixture may establish the first while the latter three remain UNKNOWN or DENY.

## Known coordination and remediation boundaries

- PR #718, #751, #756, #765 already propose adversarial, boundary, namespace and known-time tests: **review their exact diffs before adding overlapping tests**. Do not concurrently edit their test files.
- PR #742 proposes a narrow quality schedule assertion correction. The `Daily quality schedule contract` failure must be qualified on its own commit SHA; do not alter workflow cadence to satisfy a string assertion.
- Historic synthetic failures include `InvalidEvent: duplicate impact route`. Reproduce with minimal route fixtures; distinguish duplicate identical paths from contradictory impact edges, without weakening conflict rejection.
- Historic packaged Portal failures include `synthetic_customer_route_not_get_only` in negative navigation tests. Verify mock endpoint registration and expected route identity with the Portal owner; preserve GET-only enforcement.
- Integration PR #713 remains the authority for convergence decisions. No merge/rebase/cherry-pick or direct changes to its shared source paths from this quality increment.

## Exact-SHA verification receipt template

Record `repository`, `head_sha`, `workflow_run_id`, `run.head_sha`, `event`, `attempt`, `conclusion`, `test command`, `executed test count`, `failures`, `artifact links` and `observed_at`. A PASS is permitted only for an actually observed successful run **whose head_sha equals the stated SHA**. Missing run, incomplete job, or mismatched SHA => NOT_TESTED/BLOCKED; failing job => FAIL. A historical PASS never transfers to a new SHA.

## Release gate

DEMO/SIMULATION ONLY; no real GLPI, Core, Temporal, Debian, V1 :7777, V30 :7788 or LIVE side effects. No new stack, cron, credentials, deployment or runner. Policy/HITL fail-closed, `effects_allowed=false`, **LIVE NO-GO** until separately authorized and independently evidenced.

## Next owner actions

Quality owner: implement uncovered Q01–Q12 as separate additive tests after checking existing PR coverage; execute exact-SHA locally/CI. Portal owner: investigate Q12. Integrator: reconcile #713 conflicts and verify all relevant checks. Governance owner: attest independent Policy/HITL decision APIs before any claim of positive authorization. Rollback of this increment: close its dedicated PR or revert this sole document.
