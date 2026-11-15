# AIOps2 Intelligence — sandbox receipt boundary (2026-11-15)

Scope: isolated, deterministic **SIMULATION_ONLY** validation for PR #713 convergence. This is not a runtime E2E receipt, LLM evaluation, GLPI/Temporal invocation, authenticated ACL or independent Critic attestation.

Files: `scripts/aiops2_intelligence_receipt_boundary.py` and `tests/test_aiops2_intelligence_receipt_boundary.py`. New paths only; no modifications to #713, #716, #720 or #721.

The contract links a synthetic correlated SAN incident, Payments service path, evidence digests, runbook reference, structured citation list, contradictions and missing-evidence lists to distinct Analyst/Critic execution identifiers. It requires Policy DENY, HITL DENY and ITIL READ_ONLY; any malformed/missing/foreign/future/stale evidence or obvious instruction-injection pattern blocks qualification. A qualified synthetic receipt still has `effects_allowed=false`, `live=NO_GO`.

Reproduce: `python3 -m unittest discover -s tests -p 'test_aiops2_intelligence_receipt_boundary.py' -v`; `python3 -m py_compile scripts/aiops2_intelligence_receipt_boundary.py tests/test_aiops2_intelligence_receipt_boundary.py`.

**Trust limitations:** Digest syntax is not cryptographic provenance; caller-supplied tenant is not an ACL authority; distinct execution IDs do not prove independent Critic runtime; heuristic injection detection is incomplete; source timestamps are not signed. No GLPI, LLM, RAG retrieval, Temporal, DB, browser, network, Debian or LIVE call occurs. E2E SAN→Payments→Analyst/Critic→Policy/HITL→ITIL is **NOT_VERIFIED**. No automatic promotion.

Next: architect review against #713 contracts; wire trusted tenant-scoped Evidence lookup, cryptographic provenance and independently executed Critic, then disposable integration E2E and exact-head CI. Rollback: revert the three newly introduced files on this isolated branch only.
