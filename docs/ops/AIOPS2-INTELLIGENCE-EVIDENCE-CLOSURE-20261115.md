# Intelligence Evidence Closure — 2026-11-15

Scope: additive, offline, deterministic contract for PR #713 convergence. Does not execute Analyst LLM, independent Critic, GLPI, Temporal, RAG or any policy service. The trusted_evidence map is supplied by the caller; **its ACL and provenance are not authoritative** until wired to a server-side Evidence authority. Different run IDs do not establish independent Critic execution. Keyword injection screening is illustrative, not a security boundary.

Synthetic chain: SAN P1 → Payments dependency → hypothesis with citation and contradictions/missing evidence → Critic challenge → Policy DENY → HITL DENY → ITIL READ_ONLY. This is a schema/fixture demonstration, **not** E2E service execution.

Acceptance benchmark: tenant mismatch, ACL denied, stale (>24h)/future/malformed timestamp, invented citation, untrusted instructions, absent hypotheses, missing Critic separation claim, incorrect graph, LIVE mode, policy/HITL positive, effects enabled and ITIL write all yield UNKNOWN and zero effects. Positive synthetic contract also always DENIES effects and LIVE.

Reproduce at exact HEAD: `python3 -m unittest discover -s tests -p 'test_aiops2_intelligence_evidence_closure_20261115.py' -v`; `python3 -m py_compile scripts/aiops2_intelligence_evidence_closure_20261115.py tests/test_aiops2_intelligence_evidence_closure_20261115.py`.

Execution evidence: NOT_EXECUTED at authoring time. CI: UNKNOWN. No real LLM/GLPI/Temporal/E2E receipt or screenshot. Before integration, require authoritative tenant ACL, evidence signature/hash verification, runbook provenance, graph version/freshness, independently instantiated Critic and real read-only adapter tests. NO-GO LIVE.

Rollback: revert only the three new paths on the isolated branch. No overlapping files changed in #713.
