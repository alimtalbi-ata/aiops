# Intelligence authority-join negative matrix — 2026-11-16

Scope: **SIMULATION_ONLY** synthetic SAN P1 → Payments impact → Analyst hypotheses/citations/contradictions/missing evidence → Critic metadata → Policy/HITL DENY → ITIL read-only. This is an offline contract test, not an E2E integration or LLM evaluation.

Run: `python3 -m unittest discover -s tests -p 'test_aiops2_intelligence_authority_matrix_20261116.py' -v`.

Acceptance: fixture yields `synthetic_contract_ok=true` with `effects_allowed=false`, `live=NO_GO`; all 18 adversarial mutations must yield `synthetic_contract_ok=false`. Mutations: LIVE mode, wrong tenant/graph version, evidence ACL/tenant/freshness/provenance, invented citation, absent contradictions/missing evidence, unknown or cross-tenant runbook, same Critic ID, Policy/HITL ALLOW, effect enabled, ITIL write. No positive operational permission is ever returned.

Trust boundaries: ACL is a synthetic fixture, not an authoritative server decision. Runbook approval is fixture metadata, not a signed registry. Evidence timestamps and sources are fixture fields, not cryptographic provenance. A distinct Critic ID does not prove independent execution; `critic_independence=UNKNOWN` even if the caller claims independence. No prompt-injection detector is claimed: untrusted retrieved text must be isolated as data, and tested against a real RAG boundary in later integration. A syntactically clean synthetic receipt is not proof of source authenticity.

Dependencies: PR #713 canonical incident/graph/read-only contracts; Core tenant-scoped ACL and Evidence authoritative lookup; versioned CMDB/Twin edges; approved runbook registry; separate Analyst/Critic execution provenance; deterministic Policy/HITL authority; ITIL GET-only adapter. Until verified, LLM/GLPI/Temporal are `NOT_EXECUTED`, CI `UNKNOWN`, and LIVE `NO_GO`.

Rollback: revert only this document and `tests/test_aiops2_intelligence_authority_matrix_20261116.py` on the dedicated branch. No existing files or runtime state changed.
