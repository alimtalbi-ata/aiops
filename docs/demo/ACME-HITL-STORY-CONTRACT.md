# ACME — HITL/Policy/Temporal storyboard contract (synthetic-only)

The existing viewer-authenticated `POST /api/demo/explore-story/control` now includes `hitl_story` for every checkpoint. This is an **additive read-only** field, not an approval endpoint.

- `run_id`, `incident_id`, `impact_incident_id`: exactly the same labels as `scenario` and the validated six-CI ACME fixture; `run_id` is **not** a Core Run.
- `policy_command=OBSERVE` reuses `shared.simulation_policy_contract`. `policy_live_effect=DENY_LIVE_ACTION` comes from the fixture's deterministic preview; `policy_runtime_checked=false`. No Policy HTTP request was made.
- `approve`: `HUMAN_APPROVAL_REQUIRED` (no identity/approval token). `simulate`: `DRY_RUN_NOT_EXECUTED` (no Temporal workflow). `verify`: `POSTCHECK_NOT_EXECUTED`. `close`: `RECOVERY_NOT_VERIFIED`. Earlier cues: `NOT_REACHED`.
- `binding_status=MISSING`, `recipe_id=null`, `target_id=null`, `params_hash=null`, `approval_id=null`, `dry_run_receipt=null`. No HITL authorization is issued.
- `rollback=DOCUMENTED_ONLY_NOT_EXECUTED`: safe intended rollback is to discard any future isolated dry-run state and restore its initial snapshot **inside an ephemeral sandbox**, then verify postchecks. This is a plan, **not** an executed rollback.
- No backend write, tenant runtime read, secret, LLM-generated command, LIVE effect, real recovery, browser capture or authenticated evidence. Unknown/corrupt source -> HTTP 503 UNKNOWN.
- Client rejects a forged `human_decision`, Temporal completion, receipt, mismatched Run or LIVE authorization.

The existing Policy unit evaluator is separately tested for LIVE `REMEDIATE` rejection even when a caller supplies `human_approved=true`; that test is **not** a real Policy HTTP integration.

Coordination: the canonical ACME events contract in PR #133 should consume the same IDs and can later replace the fixture projection, but must not silently promote `SIM-ACME` to a Core Run. HITL stack #49→#106 is not yet integrated. No CI outcome is asserted by this document.
