# INT-06A frontend handover
Baseline 6985476f298289c14f36a8c5da0f22b734b16662. Presentation only.
The offline server projection supplies twin_consumer and signal_context. The nine
existing evidence requirements remain authoritative for the DEMO renderer.
No runtime positive projection is enabled until B/C supply an authenticated
server contract (including exact tenant, incident, Core Run, attempt, snapshot,
receipt version and independently verified terminal). An arbitrary JSON PASS,
DENY or FAIL is not an authority. Missing receipts remain MISSING; received
but unqualified evidence remains UNKNOWN. Qualified negative and positive
results must be rendered as FAIL and PASS respectively only from that future
validated server projection. No new route or orchestrator.
Run tests: PYTHONPATH=app python -m unittest discover -s tests -p 'test_acme_workbench_presentation.py'
and existing node frontend tests. Dedicated browser suite:
PYTHONPATH=app python -m unittest discover -s tests -p 'test_int06a_frontend_browser.py' -v.
Requires existing ephemeral portal test dependencies and Chromium. Never launch
runtime sandbox. Browser fixtures are DOM-only. Historical shared test untouched.
