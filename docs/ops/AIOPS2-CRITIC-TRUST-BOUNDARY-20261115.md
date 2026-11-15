# Analyst/Critic synthetic trust-boundary qualification — 2026-11-15

Scope: additive isolated files, no change to PR #713 runtime or existing contracts. Reference branch: `integration/aiops2-convergence-20261114`. This is an offline contract probe, not LLM, Temporal, GLPI, PostgreSQL, RAG, or E2E runtime qualification.

## Reproduce

```bash
python3 -m unittest discover -s tests -p 'test_aiops2_critic_trust_boundary_20261115.py' -v
python3 -m py_compile scripts/aiops2_critic_trust_boundary_20261115.py tests/test_aiops2_critic_trust_boundary_20261115.py
```

Fixture path: synthetic SAN correlated incident -> Payments dependency -> cited Evidence -> Analyst hypotheses, contradictions and missing evidence -> separately identified Critic -> Policy DENY/HITL DENY -> ITIL read-only. Fifteen adversarial mutations cover LIVE, ACL, tenant crossing, stale/future evidence, instruction injection, fabricated/missing citations, Critic identity, policy, ITIL writes, missing contradictions, missing evidence, and reversed dependencies.

Acceptance: zero effect authorization for every input; only well-formed synthetic receipts can yield `CONTRACT_VALID_SYNTHETIC`. All other cases yield `UNKNOWN` and reason codes. LIVE always `NO_GO`. Do not treat synthetic contract validity as runtime success.

Known limitations: regex injection coverage is deliberately incomplete; ACL is caller-supplied, not independently checked; Critic attestation is caller-supplied and cannot prove independence; timestamps and evidence IDs do not cryptographically authenticate provenance; no authoritative runbook retrieval, ITIL ticket read, LLM, or integration call. Thus production acceptance remains blocked pending independently signed Evidence, server-enforced tenant ACL, separate Critic execution receipt, provenance-verified RAG citations, adversarial benchmark with trusted evaluator, and real sandbox E2E with denied effects.

Rollback: revert only the two new code/test files and this document on the dedicated branch. No deployment or data mutation.
