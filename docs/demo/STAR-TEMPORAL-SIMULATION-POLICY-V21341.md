# AIOps STAR V2.13.41 — Synthetic Temporal Policy correction (HLD/LLD)

**Scope:** PR draft #36 branch only. This is a code candidate, not a production change. No Docker, Debian, n8n, Grafana, GLPI, CMDB, ticket, bridge V1 or new port is touched. No LIVE remediation is authorized.

## Evidence and root-cause narrowing

Quality Gates run [39988983803](https://github.com/alimtalbi-ata/aiops/actions/runs/39988983803) produced a **genuine GitHub CI artifact** (not a runtime screenshot): synthetic run RUN-E27F5060EC3B789B, status BLOCKED, 19 run events, 1 Analyst record, 1 Critic record, 1 Policy decision, 8 evidence records, 0 effect receipts. Analyst severity P1, Critic validated=true, Policy result BLOCKED|ESCALATE. The prior reports had shown zero counts only because the script exited before querying them; V2.13.41 fixed that instrumentation.

Source review reveals a concrete conflicting contract: the worker sent `command=EXECUTE` to Policy even in DEMO, while Policy's default `AIOPS_POLICY_EMERGENCY_STOP=true` rejects *effect* commands **before** its evidence-checked DEMO simulation branch. This is a **strong code-level explanation**, but the exact runtime Policy `reason` was not captured, so it remains a hypothesis until a fresh E2E run passes or records the reason.

## HLD — separate disposition from effect

For DEMO/REPLAY/STORY, the worker now requests Policy `command=OBSERVE` as a **non-effect disposition**; Policy may return `PASS|SIMULATE` only when Critic, evidence freshness, severity and confidence checks pass. No executable remediation is invoked. For LIVE, the worker still requests `EXECUTE`, preserving emergency stop, human approval, fencing, safety gates and the hard LIVE effect prohibition. Critic-denial paths retain their explicit `EXECUTE` request and must still fail closed.

## LLD — code and tests

- `app/shared/simulation_policy_contract.py`: pure `policy_command_for_mode` mapping; unknown modes raise ValueError.
- `app/worker/main.py`: mapping used only when assembling the normal POLICY stage input. Denial paths are unchanged.
- `tests/test_simulation_policy_contract.py`: three offline contract tests (DEMO/REPLAY/STORY, LIVE, unknown mode).
- `tests/test_simulation_policy_wiring.py`: validates actual worker wiring and evaluates Policy with mocked healthy autonomy state and emergency stop **enabled**, requiring `PASS|SIMULATE` for synthetic modes and `BLOCKED|ESCALATE` for LIVE.
- `.github/workflows/star-simulation-policy-contract-offline.yml`: isolated, no network calls after dependency install; no services started.

## Acceptance, limits and rollback

Accept only if dedicated CI passes on exact SHA **and** subsequent synthetic Runtime E2E reaches RESOLVED with Analyst, Critic, Policy PASS|SIMULATE, evidence and zero effect receipts. A technically successful n8n/Temporal run is not sufficient to assert business success. If E2E still fails, preserve the fail-closed gate and inspect the sanitized Policy reason. No authentic Debian application screenshots were collected. Revert the worker mapping commit and related helper/tests/docs on the PR branch to roll back; never merge main automatically.

## Docker packaging correction

The worker Dockerfile uses `COPY shared /app/shared` with build context `./app`. Therefore the helper must be located at `app/shared/simulation_policy_contract.py`, **not** the repository-root `shared/` directory. A previous intermediate commit used the wrong path and produced an unhealthy worker in isolated CI run 39989661396 (no production involvement). The branch has been corrected; CI now imports the same module path as the container via `PYTHONPATH=app:.` and asserts the packaged file exists. Promotion requires a new full E2E pass.
