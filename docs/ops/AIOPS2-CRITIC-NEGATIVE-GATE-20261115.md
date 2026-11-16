# Analyst/Critic synthetic negative gate — 2026-11-15

Scope: isolated source-level benchmark only; based on convergence branch and PR #713. No model, RAG provider, GLPI, Temporal, Debian or browser was invoked.

## Contract and acceptance

Run `python3 -m unittest discover -s tests -p 'test_aiops2_critic_negative_gate.py' -v` and `python3 -m py_compile scripts/aiops2_critic_negative_gate.py tests/test_aiops2_critic_negative_gate.py`.

Inputs: synthetic structured analysis with tenant, hypotheses, citations, contradictions, independently declared critic; evidence receipts with tenant, SHA-256 and UTC observation time. The checker returns sorted reason codes and never performs effects. Synthetic PASS requires same tenant, fresh evidence (default 300 seconds, no future timestamp), valid digest, known citations, explicitly assessed contradictions, and independent critic metadata. Every result returns `DENY_LIVE`, `HITL DENY` and `effects_allowed=false`. This is **not** a trusted authentication or independent-model proof: caller-supplied metadata and digest formats are not cryptographic validation, and regex injection detection is not comprehensive.

Negative benchmark: cross-tenant evidence, stale/future evidence, fabricated citation, instruction-in-evidence, contradiction, missing independent critic flag, missing citations and malformed digest must BLOCK. Deterministic replay and immutable inputs are tested. The SAN→Payments story is a synthetic fixture, not evidence of real SAN or GLPI behavior.

## Integration gate

Keep this module separate from production policy and existing Analyst/Critic files. Before any integration, validate provenance signatures/ACL at trusted service boundaries, bind citations to actual evidence content and tenant, test runbook retrieval and adversarial prompt injection beyond regex, enforce HITL server-side, compare Critic output from a genuinely independent evaluator, and run full SAN→Payments→Analyst/Critic→Policy/HITL DENY→ITIL read-only E2E in a disposable sandbox. Missing or contradictory evidence must remain UNKNOWN/BLOCKED. No LIVE promotion.

Rollback: revert only the new module, test and this note on its isolated branch. No DB schema or runtime changes.
