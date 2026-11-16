# GitHub ↔ Debian ↔ OpenAI API bridge (V1)

No Codex CLI, no SSH, no SCP. Experimental, **not installed** by this PR.

## Protocol

On GitHub issue #464, the authorized account posts one line:

```text
AIOPS2_BRIDGE_V1 status 0123456789abcdef0123456789abcdef 2026-11-16T18:00:00Z
```

The third field is a fresh random 32-character lowercase hexadecimal correlation ID.
The last field is an UTC expiry no more than 2 hours ahead.

Actions: `status` (safe local status), `openai_summary` (minimal Responses API connectivity test).
The agent posts a structured receipt as another issue comment, and saves a local receipt.
A request is attempted at most once. Failures require a new request.

## Configuration

Requires Python 3, `gh` authenticated with repo access, and a dedicated unprivileged user.
`OPENAI_API_KEY` is optional for status, required for openai_summary.
Never commit credentials. `OPENAI_MODEL` defaults to `gpt-4.1-mini`.
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
The OpenAI API invocation is independent of ChatGPT scheduled tasks and incurs separate API charges.
No automatic installation, no cron changes, no secrets provisioned.
