# AIOps 2.0 — Core Functional Hardening Review (2026-10-20)

**Author:** Abdelhalim Talbi  
**Reference:** `feat/core-analysis-quality-v2`, draft PR #21.  
**Target:** Evidence-grounded reasoning with independent Critic and deterministic, fail-closed Policy; reproducible isolated deployment, safe recovery and model-quality traceability.  
**Evidence boundary:** These changes are source-level implementations and CI test candidates. Only completed CI jobs count as executed qualification. They do not qualify real DGX inference, production CMDB/RAG, ACME twin accuracy or any LIVE effect.

## Functional deficiencies and changes

### P0 — Evidence identity was only `source + payload hash`

**Risk:** Two observations can share an identical metric payload but refer to different runs, CIs, timestamps, source identifiers or claims. A Temporal retry can also deliver a slightly different timestamp under the same external identity. Such behavior undermines the chain of diagnostic proof.

**Changes:**
- `app/shared/evidence_identity.py`: canonicalizes the entire evidence envelope (source, external ID, UTC observed time, claim, confidence, provenance and payload) and computes a SHA-256 digest.
- `app/evidence/main.py`: atomically inserts via `INSERT ... ON CONFLICT DO NOTHING RETURNING`, returns the original ID for byte-equivalent semantic replays, and returns HTTP 409 for a reused external ID with changed observation content. Caller-supplied identity contract tags are refused.
- `db/migrations/010_evidence_identity.sql`: independent unique constraints on source/full-envelope hash and source/external identity; additive query index for `provenance.run_id`.
- `app/worker/main.py`: uses the persisted `OBSERVE / STAGE_STARTED` event time to make synthetic observations replay-stable. No new clock value is created on retry.
- `app/shared/evidence_contract.py`: when evidence is stamped `identity_contract=canonical-envelope-v1`, recomputes and validates the stored digest before model inference.

**Qualification:** pure identity tests, ingestion contract tests, PostgreSQL negative index/immutability assertions and synthetic HTTP replay isolation tests. Older evidence retains its previous digest semantics; the service does not pretend legacy payload hashes prove a canonical full-envelope identity.

### P0 — A valid-looking caller could receive `ALLOW` for an unqualified LIVE effect

**Risk:** Flags such as `fencing_verified`, `human_approved` and `preconditions_verified` are supplied by the API caller. These flags are not a qualified effect execution authorization.

**Change:** `app/policy/main.py` blocks LIVE `EXECUTE`, `RESOLVE` and `REMEDIATE` even when all flags are true. Critical P1 escalation remains the first rule. Read-only LIVE `OBSERVE` can pass its independent checks without enabling an effect. Only a future complete authorized effect executor can justify revisiting the policy.

**Qualification:** unit cases cover each forbidden LIVE effect command, P1 escalation, missing proof, DEMO/REPLAY simulation boundaries and authorized read-only observation.

### P0 — Backups/restores were not truly project-isolated

**Risk:** Fixed `aiops2-` Docker volume names could reference a different running stack, while the restore script modified databases and volumes without first checking all files. Temporal visibility was not included.

**Changes:**
- `deploy/backup.sh`: binds the backup to a single verified Compose project/container and project-labelled volumes, includes both Temporal and Temporal visibility dumps, app data volumes, secret environment copy, versioned private manifest and SHA-256 verification. An incomplete marker remains if execution fails.
- `deploy/verify_backup.py`: read-only checksum, manifest/stack, dump-format, archive-integrity and path-traversal validation.
- `deploy/restore.sh`: `--verify-only` performs no mutation; actual restore requires multiple explicit confirmations including `CONFIRM_STACK_ID` and `CONFIRM_DATA_LOSS`, validates volume owner labels, stops application writers and avoids reimporting credentials automatically.
- The normal isolated target is `aiops2-rebuild`; a production-named target requires an additional separate confirmation.

**Qualification:** offline generated-fixture tests cover the valid manifest, corrupted data, wrong stack, incomplete backups, missing Temporal visibility and malicious archive paths. Live backup/restore and application-consistent recovery remain **NOT QUALIFIED**. Online volume captures are expressly classified as online snapshots, not application-consistent backups.

## Automated acceptance gates

| Layer | New positive/negative checks |
|---|---|
| Python | Canonical timestamps, identity digests, corrupted evidence, API replay/conflict/auth, restore preflight |
| PostgreSQL | Unique source/external ID, unique source/envelope hash, immutable evidence, cross-source identity |
| Temporal E2E | Synthetic run completion, persisted Analyst/Critic/Policy, zero LIVE effects, repeatable observation identity |
| Evidence E2E | Exact retry returns same evidence ID; changed claim receives HTTP 409; different run creates a separate ID |
| Safety Policy | LIVE P1 escalation; all LIVE effect commands blocked; DEMO simulation never grants execution |
| Packaging | Includes migration 010, recovery verifier, E2E scripts and machine-readable CI evidence |
| Release | All required jobs pass before cumulative ZIP is published; no production qualification claim |

## Remaining high-priority work

1. **Real LLM quality:** evaluate the actual DGX/Qwen/Mistral candidate on an expert-reviewed and held-out corpus; track P1 recall, evidence-grounded claim precision, contradiction detection, calibration, abstention and latency. Synthetic provider accuracy is not real-model accuracy.
2. **Independent evidence authorities:** qualify CMDB, changes, logs, metrics, traces, SAN/storage adapters and RAG retrieval. Require source identity, known/valid time, freshness SLAs, tenant scope and access controls; do not confuse retrieved runbook text with operational observations.
3. **PC11K5-style guarded execution:** implement durable claim/ownership epoch, fencing, precondition-hash binding, risk tier, human-role separation, effect receipt, independent verification, reconciliation and guarded rollback. No LIVE effect before this passes adversarial, concurrency and fault-injection tests.
4. **Operational durability:** test Temporal worker interruption after side effect but before receipt, duplicate/late activity delivery, PostgreSQL failover, idempotent replay, evidence TTL, backup/restore in disposable environments, and restart with restored service volumes.
5. **Only after Core qualification:** ACME digital-twin graph, multi-vendor SAN/storage/compute fault simulation, deterministic chaos campaign comparisons, operator UI, real screenshots and video demo.

## Execution policy

The source code and tests are tracked in the GitHub draft PR, not just in conversation context. The Debian host requires no ad-hoc auditing or interruption for this batch. Never use production containers to discover whether a CI fixture works. Packaging must include the exact commit, actual test artifacts and the distinction between synthetic and real-model qualification.
