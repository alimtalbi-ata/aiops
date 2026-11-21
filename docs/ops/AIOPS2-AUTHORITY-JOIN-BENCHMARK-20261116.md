# Offline SAN → Payments authority-join acceptance receipt (2026-11-16)

Scope: **SIMULATION_ONLY** Python stdlib benchmark, no LLM, RAG service, GLPI, Temporal, Docker, network, host, database or LIVE actions. Related convergence: #713; earlier independent proposals #716/#720/#721/#724/#726/#729/#732. This is a narrow test-only contribution, not another production validator.

Run: `python3 -m unittest discover -s tests -p 'test_aiops2_authority_join_sandbox_20261116.py' -v`

Synthetic chain: correlated SAN incident `inc-san-01` → versioned SAN/Payments edge → tenant-scoped evidence citation → Analyst hypothesis → contradictory alternative and missing telemetry → distinct Critic run identifier → Policy DENY → HITL DENY → ITIL READ_ONLY.

Acceptance: baseline contract PASS only for the **in-memory synthetic fixture**; 16 negative mutations must FAIL and every output must retain `effects_allowed=false`, `live=NO_GO`, `policy=DENY`. Reject invented citations, stale/future evidence, cross-tenant evidence, unknown graph edge/version/runbook, recognizable prompt injection, absent contradictions/missing evidence, same-run Critic, HITL approval and ITIL write.

Trust limits: authority is an **in-memory test fixture**, not authenticated ACL or CMDB. A `sha256:` prefix is **not cryptographic verification**. Distinct run IDs do **not prove Critic independence**; always UNKNOWN. Regex/string injection detection is not exhaustive. The fixture is not a real RAG citation, evidence signature or ITIL read.

Required integration gates before E2E qualification: authoritative tenant ACL at Core/Evidence read boundary; signed immutable evidence digests and clock-skew policy; CMDB/Twin versioned edge; allowlisted read-only runbook; independently scheduled Critic with separate inputs/provenance; prompt-injection isolation of retrieved text; Policy/HITL server-side DENY; read-only GLPI projection. Preserve UNKNOWN until witnessed.

Reversibility: revert only the two new files in this PR. No changes to convergence, V1 :7777, V30 :7788, LIVE, stacks, cron, secrets, or existing tests.
