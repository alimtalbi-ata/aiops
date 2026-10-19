# Historical Portal Recovery — Independent Review

**Author:** Abdelhalim Talbi  
**Review date:** 2026-10-19  
**Scope:** Uploaded recovery archives from 14:41 and 15:44, source hashes, route inventory, Python syntax, and selected security-sensitive code paths.  
**Evidence boundary:** Static inspection only. No dependency installation, application startup, database access, browser test, API integration test, or production test was performed.

## 1. Archive integrity

| Artifact | Size | SHA-256 | Result |
|---|---:|---|---|
| `AIOPS-HISTORICAL-PORTAL-SOURCE-RECOVERY-20261019-154435.tar.gz` | 856,801 bytes | `829bec97028fbe21a96b8fbcc77fdb8c3092f304f5a8665106edc2c87b8180e4` | PASS: matches uploaded sidecar |
| `AIOPS-HISTORICAL-PORTAL-SOURCE-RECOVERY-20261019-144103.tar.gz` | 756,799 bytes | `4cc9d5bdfc53819c104fc6ab0dbfe4f5a02aa6d4581191f9256de551fbd663af` | PASS: matches uploaded sidecar |

Both archives were listed and extracted into isolated temporary directories using a safe extractor that rejected absolute paths, parent traversal, and links. No unsafe TAR member was found.

The 15:44 archive contains 48 TAR entries: 36 regular files and 12 directories. Its internal `SHA256SUMS` contains 35 file entries; **all 35 match** the extracted bytes.

The 14:41 archive contains 45 TAR entries: 33 regular files and 12 directories. Its internal checksum list has 33 entries; 32 source-file entries match. The only mismatch is the `./SHA256SUMS` self-entry: it records a digest of the checksum file itself, which cannot stably match the final file including that entry. Treat this as a manifest self-reference defect, not evidence that the source payload failed its checks. The external archive hash and all other listed files pass.

## 2. Source inventory and syntax

| Source | Lines | Bytes | Python compile |
|---|---:|---:|---|
| R33 `main.py` | 2,913 | 75,846 | PASS |
| V1 `main.py` | 4,391 | 118,463 | PASS |
| V145 `main.py` | 4,649 | 124,847 | PASS |

Python compilation passed for all three source files. This checks syntax only; it does not prove imports resolve, startup succeeds, routes work, or dependencies are secure.

The 15:44 package includes:
- R33 source and assets;
- V1 source and assets;
- V145 source and assets;
- V1/V145 and R33/V145 textual diffs;
- a source inventory and heuristic static-analysis report.

The package manifest explicitly says runtime qualification is not implied and that PC11K5 fencing/ownership behavior must not change.

## 3. Route-level comparison

The route inventory extracted from decorators reports:

| Comparison | Added routes | Removed routes |
|---|---:|---:|
| R33 → V1 | 19 | 0 |
| V1 → V145 | 0 | 3 |
| R33 → V145 | 19 | 3 |

V1 adds the operations overview/events, demo director state/action, demo image/video routes, R35 authority/chapter routes, story pages, director run detail, and V145 cockpit redirects.

V145 removes these three GET routes that existed in V1/R33:
- `/api/v1/cmdb/impact/{asset}`
- `/api/v1/incidents/{incident_id}/snapshot`
- `/api/v1/incidents/{incident_id}/stream`

These removals may be intentional, but they are compatibility regressions until the UI consumers and replacement routes are identified. The stream route in particular should be checked against operator timeline/live-update expectations. Do not restore them blindly; compare consumers and API contracts first.

## 4. Security finding — fail-open admin-token helper

In all three source versions, the helper is effectively:

```python
ADMIN_TOKEN = os.getenv("LIVE_CONSOLE_ADMIN_TOKEN", "")

def _admin_ok(token):
    if ADMIN_TOKEN and token != ADMIN_TOKEN:
        raise HTTPException(403, "invalid live console admin token")
```

This is fail-open when `LIVE_CONSOLE_ADMIN_TOKEN` is absent or empty: the check does not reject a missing token. Static inspection found only one call site of `_admin_ok` in each version, associated with the demo scenario path; the helper is not a general authorization boundary for the API.

Implications:
- Configuration omission disables this token check rather than failing startup.
- Other state-changing endpoints must not be assumed protected by this helper.
- The current evidence does not establish network exposure or prove an exploit in a deployed instance.

Required correction before external exposure:
1. Fail startup/preflight if an admin token is required but missing or weak.
2. Use a centralized, explicit dependency for every privileged mutation; default deny.
3. Compare secrets with constant-time comparison and never return/log the secret.
4. Prefer the established operator identity/proxy boundary where defined; do not trust unverified forwarded identity headers.
5. Add tests for unset token, empty token, missing request token, wrong token, valid token, and all privileged routes.
6. Separate read-only access from DEMO/chaos/HITL mutations and enforce explicit DEMO mode. Never let a demo endpoint authorize LIVE remediation.

This aligns with GitHub issue #15, which tracks portal authorization hardening.

## 5. Compatibility and product findings

- V145 has a larger Python entrypoint than V1 (124,847 vs 118,463 bytes) and R33 (75,846 bytes); size alone is not evidence of improved quality.
- V145 adds `run_id` to the Activity schema and makes DemoScenario accept `scenario_id` with optional `scenario`. This may improve identity propagation and scenario compatibility, but consumers and persistence schema must be checked.
- V145's route inventory lacks the three V1 routes listed above; this needs explicit UI/API consumer review.
- The static analyzer flags many JavaScript `innerHTML` assignments. These are review leads, not confirmed XSS findings. Trace untrusted values and verify escaping/safe DOM construction before raising severity.
- R33/V1 include a bundled requirements file; the V145 export does not include its own requirements file. Dependency closure for V145 therefore remains unproven from this package.
- Multiple large HTML assets have identical hashes across V1/V145 despite the differing entrypoint and CSS/JS assets. This can represent intentional reuse, but it makes route-to-asset mapping and stale UI references important to test.

## 6. Reuse decision matrix

| Capability | Decision now | Reason / gate |
|---|---|---|
| R33/V1/V145 source packages | Preserve as references | Integrity verified; not a deployable release |
| Operations overview/events | Candidate: adapt behind a read-only adapter | Verify schema, freshness, auth, error states, and canonical Core contract |
| Demo Director / campaign studio | Candidate: adapt for isolated DEMO only | Verify auth, deterministic seeds, cleanup, idempotency, and synthetic labels |
| HITL endpoints and decision UI | Unknown pending deeper review | Verify identity, authorization, audit append-only semantics, approval resume/close and replay behavior |
| Evidence/GLPI endpoints | Candidate: adapt behind typed evidence adapter | Verify provenance, timestamps, freshness, permissions, redaction, and source failures |
| V145 route removals | Compatibility risk | Determine consumers and replacement contracts before adopting V145 routing |
| Admin token helper | Reject as sufficient authorization | Fail-open on missing configured token; too few call sites for centralized protection |
| Legacy `innerHTML` sites | Needs targeted review | Static heuristic only; prove source-to-sink paths and escaping |
| Whole historical portal | Do not import wholesale | Duplicate control plane and unqualified side effects risk |

## 7. Qualification plan

1. Define the portal's operator identity model and trusted deployment boundary.
2. Build a route inventory classifying every route as public-read, authenticated-read, DEMO mutation, HITL decision, or privileged operation.
3. Add default-deny authorization and tests before exposing routes.
4. Compare each removed route against the V1/V145 frontend consumers.
5. Add contract tests for activity/run identity, scenario IDs, evidence provenance, and API error responses.
6. Run isolated tests with synthetic fixtures and a disposable database only.
7. Verify idempotency, retries, cleanup, replay and audit trails.
8. Re-run PC11K5 fencing/ownership/concurrency regression tests; no historical portal change may weaken claim → fencing/ownership → preconditions → effect → evidence → reconciliation.
9. Only after those gates, propose a small adapter-based PR. No active runtime changes are authorized by this report.

## Final status

**Archive integrity: PASS. Source syntax: PASS. Semantic/API/UI qualification: NOT YET RUN. Production qualification: NOT RUN.**  
No application or active runtime was changed during this analysis.
