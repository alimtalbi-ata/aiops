# AIOps 2.0 — RC1.2 Reconstruction Release and Acceptance Plan

**Version:** `2.1.0-core-rc1.2`  
**Author / architecture:** Abdelhalim Talbi  
**Tracking:** PR #21, `feat/core-analysis-quality-v2`  
**Baseline proof:** [GitHub Actions #39386565967](https://github.com/alimtalbi-ata/aiops/actions/runs/39386565967), commit `4dc3032300452612f49e2ef98d44be29f835f9ca` (RC1.1)  
**Release proof:** The corresponding RC1.2 workflow and artifact must pass separately; prior release success cannot be reused as evidence for changed code.

## Scope, progression and boundaries

```text
                           ONE CANONICAL AIOPS2 PROJECT
                     Host side: Docker Compose, isolated ID
                                         |
            +----------------------------+----------------------------+
            |                            |                            |
     Portal / API                  Core / PostgreSQL              Observability
     presentation only             run+event ledger               Grafana/Prometheus
                                         |
                                 Temporal (durable)
                                         |
                                   Worker activities
                                         |
                     +-------------------+--------------------+
                     |                   |                    |
                Twin+Evidence       LLM Analyst          Independent Critic
               provenance/hash      advisory JSON         challenge/abstain
                     |                   |                    |
                     +-------------------+--------------------+
                                         |
                              Deterministic evidence guard
                                         |
                                Policy / HITL / Fencing
                                         |
                                    DEMO: SIMULATE
                                    LIVE: BLOCKED
```

### Priority ordering

1. **Core correctness:** PostgreSQL canonical ledger, optimistic versions, immutable evidence/decisions, Temporal replay, deterministic policy. A model cannot authorize execution.
2. **Reasoning quality:** Analyst and independent Critic, fresh evidence, prompt injection resistance, contradictory/unsupported claims, record of provider/model/prompt/dataset and evaluation gate.
3. **Operational reproducibility:** isolated Compose deployment, schema upgrades, health/readiness, private backup, verify-only restore and release checksums.
4. **Next milestone:** replace synthetic provider with actual qualified DGX/local LLM, build larger blinded evaluation corpus and calibrate decision thresholds; then ACME digital twin, graph/chaos, and presentation/video.
5. **Separate restricted milestone:** LIVE evidence adapters, scoped CMDB/RAG, manual dual approval, ownership fencing and independently verified remediation/rollback.

## RC1.2 work package — concrete changes

- **Early retirement rejection:** `deploy/install.sh` and `deploy/big-bang.sh` reject `RETIRE_LEGACY=1` *before* initializing secrets, building images, or touching any Docker resource. Retirement is a separate explicit operator decision after backup and Core qualification.
- **Namespace isolation:** `deploy/install-isolated.sh` sets `aiops2-rebuild` project identity, private networks/volumes/container names and alternate dashboard ports. Default bind address remains `127.0.0.1` for safer remote access through SSH tunnels.
- **Stack-scoped qualification:** `tests/qualification.sh` rejects wrong Compose project ownership instead of accepting arbitrary healthy containers with matching names. `tests/seed-demo.sh` scopes PostgreSQL checks to the selected Compose service and validates nonempty topology.
- **Private diagnostics:** `deploy/diagnose.sh` derives service state through the active project, and `deploy/redact_logs.py` masks secret *values*, bearer credentials, inline secret assignments and embedded URL passwords. A redaction failure results in no saved log file.
- **CI regression gates:** `tests/test_redact_logs.py` and `tests/lifecycle-safety-contract.sh` run in unit/release qualification; existing SQL, unit, Temporal E2E, AI scoring and complete packaging gates remain mandatory.

## CI coverage and interpretation

| Gate | What it proves | What it does not prove |
|---|---|---|
| Source, unit and safety contracts | API types, evidence rules, policy defaults, redaction and lifecycle refusal | Accuracy of a real LLM |
| PostgreSQL empty + upgrade migrations | Schema creation, immutable triggers, migration replay and upgrade compatibility | Real operational database backup consistency |
| Temporal synthetic E2E | Portal/Core/worker orchestration, Analyst/Critic/Policy ledger, no LIVE effect | Fault-free performance under site load |
| Blinded deterministic model fixture | Scoring mechanics, cited references, staleness/contradiction/injection tests | Expert-adjudicated RCA accuracy |
| Cumulative release ZIP verification | Included scripts/docs, checksums, bounded evidence, reproducible commit | Deployment on `SRV-DEB-05` or actual vendor arrays |

**Release rule:** Ship the cumulative ZIP only if `release-kit` completes successfully for the **current** branch head, with both `09-Qualification/runtime-e2e-*.json` and `09-Qualification/ai-core-evaluation.json` declaring PASS. The kit `RELEASE-MANIFEST.txt` must state `real_model_qualification=NOT_RUN` and `production_qualification=NOT_RUN`. Do not turn PASS fixtures into real-model claims.

## Operator procedure — after offline qualification

### A. Verify the received ZIP on Windows

Download the exact `AIOps-2.1.0-core-rc1.2-...zip` and its `.sha256` from the qualified release artifact. Run `Get-FileHash -Algorithm SHA256` and compare with the release checksum. This is read-only and does not touch Debian.

### B. Transfer and deploy (when approved)

Upload the received ZIP with `scp` to `/home/aiops/`; do **not** use `/in` or `/out`. Extract to a fresh directory in `/home/aiops/`, preserve the source tree, and execute:

```bash
bash deploy/install-isolated.sh
```

This intentionally does not invoke legacy retirement. For secure Windows access, forward remote loopback port `17777` over SSH instead of binding the service publicly.

### C. Qualify & preserve results

```bash
bash tests/qualification.sh
bash tests/seed-demo.sh
bash deploy/diagnose.sh
bash deploy/backup.sh
```

Backups include credentials and must remain private, protected and encrypted; review any diagnostic bundle before sharing. The restore path starts with `bash deploy/restore.sh --verify-only <backup-directory>`, and a destructive restore always requires explicit independent confirmations.

## Go/no-go

**GO for isolated, synthetic reconstruction:** exact RC1.2 CI is PASS, ZIP+SHA256 verify, no legacy resources touched, Demo run resolves with Analyst/Critic/Policy records and effect_receipts=0.

**NO-GO for LIVE/autonomous remediation:** any missing source qualification, evidence freshness, real-model evaluation, role-bound human approval, ownership/fencing, independent verification or rollback testing.

**Next deliverable:** a dedicated real-model evaluation kit with a blinded domain-specific corpus (SAN path loss, Oracle latency, ESXi FC, replication lag, capacity) and a discrepancy report comparing expected labels to actual Analyst, Critic and deterministic policy outputs.
