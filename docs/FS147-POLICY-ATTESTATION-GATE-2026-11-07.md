# FS147 Policy remote-attestation gate — 2026-11-07

Scope: Worker only, no changes to Portal FS1097/FS1113 or Core contracts.
This increment supplies `worker.fs147_policy_attestation.require_policy_attestation`.
It must be called **inside the authenticated Policy transport**, on the raw
remote reply, **before** `check_fs147_policy` normalizes any legacy fields:

```python
from worker.fs147_policy_attestation import require_policy_attestation

def policy_post(payload):
    raw = authenticated_policy_client.post_check(payload, timeout=5)
    return require_policy_attestation(raw, current_request, current_evidence_id)
```

The binding of `current_request` and `current_evidence_id` must be per invocation,
not mutable global state. The remote service must echo all six identity fields;
a legacy reply without them is UNKNOWN, not a verified PASS. Do not enable
this transport until the Policy owner supports these fields. The Worker
composition remains fail-closed if this gate raises.

Integration contract proposed to Policy owner: authenticated response must
attest tenant_id, actor_id, incident_id, run_id, integer ticket_id=147,
evidence_id, state, decision. A PASS is acceptable only for SIMULATE; all
other states are non-authorizing. Core owner must provide atomic durable
claim/resume status keyed by tenant/incident/run/ticket, without a second
bridge observation on duplicate run; do not modify Core here. Bridge owner
must attest /fs-lab, read_only=true, df/du/ls, evidence_id, timestamp and
source; Worker rejects stale evidence (>5 min or >30s future).

Negative tests: `python -m pytest -q tests/test_fs147_policy_attestation_20261107.py`.
These are local contract tests, **not** proof of authenticated Debian transport,
Core durability, GLPI 147 mutation or end-to-end execution. STOP_AUTO, no SAN,
no destructive commands, no truncate, no HITL or RESOLVED transitions.

Qualification: CODE committed; CI unknown; HOST unknown; EXECUTED E2E NO_GO.
