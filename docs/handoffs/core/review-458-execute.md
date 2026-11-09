# Agent 1 — Core.execute review delivery (#458)

UTC: 2026-11-09T21:25:32.324759+00:00
Role: Core reviewer. Delivery branch: agent/core/458-review-execute.
Review only: no application changes, merge, deployment or production access.
The delivery commit is documentation only; its HEAD is not an application qualification target.

## Exact examined sources

- Initial review target: agent/integration/462-isolated-candidate at 3f2e361c1997ff14a490bb240eea902820a1302f.
- Incremental review target: e0fc66c3bc8f56cace0074de2f0a07d5bb551303.
- Scope: only app/core/main.py::execute; adjacent Worker response contract, receipt schema and existing focused tests consulted to interpret it.
- Incremental diff: four files, CI and qualification documentation only. app/core/main.py and tests/test_candidate_core_execute.py are byte-identical between these targets. No full validation repeated for the increment.
- Conclusions apply only to these examined sources. Subsequent changes require relevant delta review.

## Findings

1. P1 — app/core/main.py:271-273 (both examined SHAs): existing durable receipt identity is not checked against the canonical Run/workflow identity. Any nonempty stored workflow is returned as success. Offline reproduction with Run RUN-1 and a stored RUN-OTHER returned {run_id: RUN-1, workflow_id: RUN-OTHER, idempotent: true}, without contacting Worker. This defeats the identity check applied to fresh Worker responses. An old or inconsistent receipt must not be acknowledged as a verified canonical workflow.
2. P2 — app/core/main.py:289 (both examined SHAs): all requests.RequestException failures, including Worker HTTP rejections raised by raise_for_status, become HTTP 503. A non-transient upstream 422 is therefore reported as service unavailable. Offline reproduction of an upstream rejection exception confirmed HTTP 503. Error handling does not distinguish HTTP rejection from transport unavailability.

Previously reported baseline issues concerning missing LIVE/mode refusal, replay after Run progression and unvalidated fresh Worker identity are addressed in the examined candidate. The existing-receipt identity and HTTP error findings above remain.

## Tests actually executed

Exact 3f2e361c sources were exported to a temporary directory without switching the application checkout. requests==2.32.4 was installed under /tmp for the offline tests. No application startup or external service connection occurred.

Command: python -B -m unittest discover -s <temporary exact-source tests directory> -p test_candidate_core_execute.py -v
Result: 7 tests executed, 7 PASS.
Coverage: LIVE rejection; corrupt/unsupported persisted mode rejection; durable receipt replay after state progression; progressed Run without receipt rejection; empty receipt identity rejection; malformed or foreign fresh Worker identity rejection; progressed LIVE rejection.
Additional offline reproductions: foreign stored receipt accepted; Worker rejection exception mapped to 503 (findings above).
Initial attempt: test module import failed because requests was absent; no substantive test executed in that attempt. After the isolated dependency installation, all seven tests executed and passed.
Test fixture extracts the actual function via AST and mocks DB/HTTP; it does not verify real PostgreSQL transaction durability, concurrency, Temporal execution or HTTP integration. The seven passing tests do not cover the two findings sufficiently to dismiss them.

## Increment and CI

The e0fc66c3 increment adds the candidate push trigger and the seven-test CI step while retaining existing jobs and permissions, plus qualification/PR documentation. These additions do not change either finding. No rerun of unchanged application tests for that increment.
CI exact-SHA run URLs/results: UNKNOWN; no GitHub Actions success claimed. Debian receipt freshness: UNKNOWN. E2E: NOT_VERIFIED. FS1250: HOLD. No authenticated GLPI readback, production PostgreSQL access, Debian deployment or live action performed.

## Ownership, blockers and handoff

Core implementation remains PREPARATION ONLY: exclusive app/core/** ownership and a Core implementation PR base were not approved in this session. This delivery is an explicitly requested sanitized review document, not implementation authorization. No PR opened.
GitHub API previously returned Forbidden; no API bypass or renewed API write attempted for this delivery. Git HTTPS publication is a separate authorized route; its result must be reported separately.
Next owner: Debian CLI / Integration for overnight coordination. Address findings through the approved writer and a separate commit, retain exact-SHA evidence, then request focused delta review. No new task starts after this delivery.
Rollback: remove/revert only this documentation commit if needed; no application or Debian rollback is required.
