# FS147 — evidence gates for real read-only Worker integration (2026-11-06)

This is a **NO_GO** integration checklist, not evidence of a deployed pipeline. Reference: [FS364](FS364-ARCHITECTURE-REPRISE-2026-11-06.md).

## Current boundary

`worker/fs147_service_pipeline.py` composes bridge → Analyst → Critic → Policy using **injected callbacks**. The existing tests exercise contract stubs and the in-process Policy evaluator. None proves a live authenticated call to Debian fs-lab, Core, GLPI or Analyst/Critic/Policy HTTP endpoints. Do not label such tests E2E.

## Required authenticated host-side bindings (not inferred from GitHub)

1. Establish a read-only, allowlisted bridge transport to the **fs-lab container**, not Core's filesystem. Only `df`, `du`, `ls` on `/fs-lab`; record command exit codes, captured output, bridge identity, `collected_at`, `evidence_id` and measurement. Never use historical 92% as a fresh measurement.
2. Core must allocate or retrieve the *existing* incident and run, atomically reserve the idempotency key and durably bind `alert_fingerprint → incident_id → run_id → evidence_id → glpi_ticket_id=147`. Replays must not create another run or ticket. A local process dictionary is insufficient.
3. Authenticate Analyst, Critic and Policy separately, and verify tenant/actor/incident/run/ticket/evidence correlation at each boundary. Refuse omitted or contradictory identity fields at the production transport boundary. Persist actual request/response timestamps and redacted correlation logs.
4. Before any call, enforce STOP_AUTO and DEMO scope. Only `OBSERVE`/`NO_EFFECT` is in scope. Neither the bridge nor any downstream callback may delete, truncate, fill the lab, approve HITL, modify ticket status or transition RESOLVED.
5. Compare GitHub code to the Debian checkout, Compose overlays and active image digests before deployment; do not overwrite a dirty checkout or other demos. Validate the host's endpoint contracts, certificates, service identities and ACLs **on the host**; no guessed URL or credential is acceptable.

## Host evidence needed to lift NO_GO

Record, without secrets, a single fresh `run_id` and ticket 147 across the alert, Core durable claim, bridge command evidence, Analyst response, Critic response, Policy decision and GLPI readback. Include timestamps, HTTP statuses, service/image digests and immutable evidence IDs. A test-only fabricated RUN or bridge payload is not evidence.

## Negative tests to execute against the same integration

- Duplicate concurrent requests and replay after process restart: one durable Core claim, no second ticket, no downstream duplicate effects.
- Missing/stale `df/du/ls`, invalid timestamp, mismatched ticket 146, missing evidence ID, bridge offline: BLOCKED/NO_EFFECT and no Analyst call.
- Empty Analyst findings or unavailable Analyst: BLOCKED/NO_EFFECT and no Critic call.
- Critic refusal or wrong run/evidence: BLOCKED/NO_EFFECT and no Policy call.
- Policy denial, missing/contradictory correlation, unavailable Policy: BLOCKED/NO_EFFECT; no HITL approval and no RESOLVED.
- STOP_AUTO active: zero external calls, including Core claim.

Contract-only regression command:

```bash
python -m pytest -q tests/test_fs147_service_pipeline.py tests/test_fs147_service_fail_closed.py tests/test_fs147_policy_reply_correlation.py tests/test_fs147_policy_engine_integration.py
```

**Qualification rule:** report CODE, CI, HOST, EXECUTED and BLOCKED independently. A GitHub commit or passing mocked tests does not prove a live observation. No SAN dependency is permitted.
