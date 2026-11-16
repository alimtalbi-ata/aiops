# GitHub ↔ Debian bridge (V1)

No Codex CLI, no SSH, no SCP. Experimental, **not installed** by this PR.

## Protocol

On GitHub issue #464, the authorized account posts one line:

```text
AIOPS2_BRIDGE_V1 status 0123456789abcdef0123456789abcdef 2026-11-16T18:00:00Z
```

The third field is a fresh random 32-character lowercase hexadecimal correlation ID.
The last field is an UTC expiry no more than 2 hours ahead.

Actions in the proposed revision: `status` (safe local status), and
`acme_receipt_status` (fixed-path, read-only inspection of the existing Debian
ACME receipt, returning **only** status, schema and sandbox-safety booleans).
The latter never executes the scenario, never reads Docker, never exposes
incident/ticket IDs, and **does not** establish a readiness verdict or deployed SHA.
The currently installed earlier pinned agent only supports `status`; a new
pinned version requires explicit review and operator installation.
 Paid OpenAI API calls are deliberately unsupported.
The agent posts a structured receipt as another issue comment, and saves a local receipt.
A request is attempted at most once. Failures require a new request.

## Configuration

Requires Python 3, `gh` authenticated with repo access, and a dedicated unprivileged user.
No API key is needed or supported. Never commit credentials.
Set `BRIDGE_ISSUE`, `BRIDGE_AUTHORIZED_LOGIN`, `BRIDGE_STATE_DIR` as necessary.

Install from a **reviewed pinned SHA**, not from a moving branch.
Run `python3 -B agent.py` manually first and verify receipts.
For 30-second cadence, use a systemd timer or two cron entries (at :00 and sleep 30)
with the same local state directory. The agent has its own nonblocking flock.

## Limits

This is a proof of transport, not a production agent. It never executes model-generated
commands, never invokes shell scripts, and never touches Docker, databases, or deployment.
A GitHub author-name check is not sufficient for high-impact actions; those require stronger
authorization, explicit action policies, provenance, input bounds, and audited approvals.
This bridge has no OpenAI API integration or API charges; it does not externally trigger ChatGPT scheduled tasks.
Deployment of updates requires a reviewed pinned SHA; no cron changes or secrets are provisioned by this PR.
