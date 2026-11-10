# FS147 — Twin interchangeable / adapter boundary (candidate 2026-11-08)

Owner: Twin. Baseline: GitHub candidate only; Debian host UNKNOWN. Based on PR #451 fixture contract, not a replacement for its historical isolation tests.

Reference contracts: [product architecture](architecture/AIOPS2-PRODUCT-REFERENCE-ARCHITECTURE.md), [workpackages](architecture/AIOPS2-RECONCILIATION-WORKPACKAGES.md), [team contract](architecture/AIOPS2-TEAM-CONTRACT-20261108.md) on `audit/preserve-debian-48h-20261108`. These are **proposals**, not deployed APIs.

## Deliverable
`tests/test_fs147_twin_adapter_boundary_contract.py`: pure Python unittest, deterministic replay, two independent tenant/source/event/correlation/incident/RUN/Evidence identities, graph and namespace, observation timestamp and metric, resource and dependency edge. Rejects cross-tenant identity substitutions, foreign Evidence edge, missing canonical envelope provenance and nondeterministic timestamp. The fixed fixture label `147-FIXTURE` is **not** GLPI ticket 147; never create a ticket.

Run: `python3 -m unittest discover -s tests -p 'test_fs147_twin*contract.py' -v`. No Docker, network, framework, external services or writes.

## E2E receipt / scope
Source event -> resource -> incident -> run -> evidence: QUALIFIED_FIXTURE only. Analysis/Critic, Policy/HITL, Temporal/Worker, ITSM external ref/readback, append-only audit: UNKNOWN for real incident 147. Twin SAN invocation for /fs-lab: UNVERIFIED; exclusion provisional pending real lineage and FS364 source. No SAN/FS cross-graph dependency is authorized. Never infer a GLPI ticket absence from missing xref. Preserve historical GLPI #147 without recreation.

To graduate from fixture: read-only collect incident 147 -> exact RUN -> Evidence -> dependency graph from Debian APIs/DB with timestamps and source provenance, compare against Twin SAN graph, reconcile source/event identity and ITSM readback. Capture sha/image digest and receipt per stage; do not claim E2E PASS for missing steps.

## Handoff / gates
- Integration: candidate-only; verify FS364 by immutable SHA, compare Debian live contracts and adapter shape; do not merge.
- Core: provide read-only 147 incident/RUN/external-ref lineage and lookup-before-create status.
- Worker: provide read-only Temporal/Worker/Evidence provenance, no action or approval.
- Portal: show UNKNOWN and fixture-vs-live distinction; no synthetic success.
- Twin: maintain deterministic isolation and negative tests.

CODE = candidate commit; CI = UNKNOWN until SHA-specific workflow; HÔTE = UNKNOWN; EXÉCUTÉ = local execution unverified / live E2E UNKNOWN. Risk: hard-coded fixture identities deliberately cannot validate arbitrary customer payloads; follow-on schema mapping must be qualified against actual adapter contracts. Rollback: close candidate PR / revert isolated test and document commit only. Approval required before merge or deployment.

If later Docker testing is approved, publish test container **first** on `aiops2-rebuild-public` with explicit port mapping, then attach control/integration/observability one by one and recheck runtime PortBinding and HTTP after each. No production network changes.
