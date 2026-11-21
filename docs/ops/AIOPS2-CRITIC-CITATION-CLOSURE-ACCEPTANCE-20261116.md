# Analyst/Critic citation-closure acceptance delta — 2026-11-16

Status: **OFFLINE CONTRACT ONLY / LIVE NO-GO**. Target: PR #713, `integration/aiops2-convergence-20261114`. This document is a review-only increment, not evidence of LLM, GLPI, Temporal, or live execution.

## Sandbox scenario

Synthetic SAN P1 correlated to Payments impact through a versioned dependency path. Analyst output must contain ranked hypotheses, evidence IDs and source citations, contradicting observations, missing proofs, and an allowlisted read-only runbook reference. A separately executed Critic must challenge the causal chain and citation closure; different execution IDs alone **do not** prove independence.

## Negative acceptance matrix

1. Invented citation / citation absent from evidence manifest: BLOCK.
2. Evidence from another tenant or missing server-authoritative ACL: BLOCK / UNKNOWN.
3. Evidence older than 24h, future-dated or missing timezone: BLOCK.
4. Retrieved text containing instruction override or LIVE approval request: treat as untrusted data, BLOCK.
5. Dependency graph version missing, SAN→Payments edge unproven: UNKNOWN / BLOCK.
6. Runbook not allowlisted by trusted authority: BLOCK.
7. Missing contradiction, missing-proof register or unsupported hypothesis: BLOCK.
8. Critic self-review, shared execution context or unverifiable provenance: UNKNOWN; never claim independent.
9. Policy ALLOW, HITL APPROVED, ITIL WRITE or effects_allowed=true in sandbox: BLOCK.
10. Hash shaped like SHA-256 without trusted content binding: UNKNOWN, not provenance proof.

## Required receipt

`scenario_id`, `source_sha`, `fixture_sha256`, `tenant`, `run_id`, `incident_id`, `dependency_graph_version`, `evidence_manifest`, `citations`, `hypotheses`, `contradictions`, `missing_proofs`, `runbook_id`, `analyst_execution_provenance`, `critic_execution_provenance`, `policy=DENY`, `hitl=DENY`, `itil=READ_ONLY`, `effects_allowed=false`, `live=NO_GO`. Unknown fields remain UNKNOWN rather than assumed true.

## Exit criteria

Synthetic deterministic negative tests must reject every mutation; actual integration requires authoritative tenant ACL pre/post retrieval, source-bound cryptographic evidence hashes, trusted runbook registry, independent Critic execution receipt, and read-only ITIL response attestation. CI PASS only with exact-head workflow conclusion and artifact. No LIVE promotion from synthetic evidence.

## Run record

An independent local scratch Python prototype was exercised with `python -m unittest -v test_aiops2_critic_citation_closure`: **2 tests passed**, including **18 negative subcases**, and `python -m py_compile *.py` succeeded. **This prototype is not committed in this PR and its result does not qualify this GitHub SHA.** SHA-256 of local scratch module: `9855dc6dfd410852839f4d3b38fdaef632d4fa0db899f49abd2385ab736c8dae`; scratch test: `8d3cf13207f646fe66c3f3d8d3f0f9a19d5eb453c6f6026726530fba1829c07e`. No CI, E2E, LLM, GLPI, Temporal or Debian run is claimed.

## Coordination / next action

Avoid editing the many PR #713 application, test and workflow files; review this isolated acceptance delta against #713 and existing #716/#720/#721/#724/#726/#729/#732/#737/#740 rather than creating another competing runtime gate. Owner must implement trusted evidence/ACL/runbook adapters and independent Critic provenance, then run exact-SHA qualification. Rollback: revert this documentation-only commit. No merge/rebase/cherry-pick/deploy/SSH/cron or external effects.
