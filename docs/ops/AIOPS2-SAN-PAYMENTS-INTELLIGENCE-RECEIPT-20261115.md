# SAN → Payments → Analyst/Critic → Policy/HITL → ITIL (offline receipt)

2026-11-15. Scope: deterministic **SIMULATION_ONLY** receipt, not a real end-to-end qualification. Base: convergence PR #713 HEAD `d1763c90595f0714347c86cd55f86e60f44e236c`. Follow-up to isolated Critic PR #716; no overlapping edits.

Run from repository root: `python3 -m unittest discover -s tests -p 'test_aiops2_sandbox_chain_receipt.py' -v` and `python3 -m py_compile scripts/aiops2_sandbox_chain_receipt.py tests/test_aiops2_sandbox_chain_receipt.py`.

Expected: eight adversarial subcases (LIVE, tenant mismatch, wrong dependency, missing evidence, cross-tenant, stale, fabricated citation, positive HITL), malformed inputs, and a nominal synthetic fixture. The receipt always returns `DENY_LIVE`, `HITL DENY`, `effects_allowed=false`, and `LLM/GLPI/Temporal NOT_EXECUTED`. An untrusted flag claiming independent Critic **cannot** prove independence: `CRITIC_INDEPENDENCE_UNATTESTED` is always present. ITIL is a read-only intent only, not a GLPI request.

Acceptance for future integration: authoritative actor/tenant ACL at API boundary; evidence integrity/provenance and freshness; source-backed dependency rather than fixture path; independent Critic execution with identity and trace; explicit contradiction/missing-proof citations; adversarial prompt-injection tests on retrieved text; Policy/HITL deny receipt from an independent engine; read-only GLPI transport receipt; exact-head CI and isolated E2E. All currently UNKNOWN/NOT_EXECUTED.

No network, secrets, databases, Docker, SSH, deployment, merge or LIVE. Rollback: omit/revert the three new files on this isolated branch. No V1/V30 runtime modification.
