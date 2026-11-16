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

## Operator-controlled promotion of the ACME read-only diagnostic

**Not an installation command.** This checklist requires a separately approved
Debian change window. The bridge currently installed on SRV-DEB-05 is an older
pinned `status`-only version. GitHub CI cannot attest Debian deployment.

1. Review exact candidate commit `a6242cf0eb1e21295ee6aa1c47358f707a9aa1e4`
   and its GitHub Actions run `43933548513` (offline contracts PASS).
   Verify the code only reads the fixed ACME receipt path and never executes
   the E2E runner, Docker, arbitrary shell, Codex, or paid OpenAI API.
2. An authorized operator records a change approval and maintenance window,
   the currently installed SHA, file hashes, current timer configuration and
   a tested rollback method **before** touching the Debian agent.
3. Install only reviewed bytes pinned to the approved SHA, using the existing
   operator-managed deployment mechanism; never install from a moving branch,
   never change the poll cadence, credentials, issue authorization, or state
   directory as part of this change. No automatic installation is requested.
4. First check `status` still works. Then submit a **new** command of form
   `AIOPS2_BRIDGE_V1 acme_receipt_status <32-lowercase-hex> <UTC-expiry>`
   from the authorized GitHub account on issue #464, with expiry no more
   than two hours ahead. Do not reuse correlation IDs or prior comments.
5. Expect `NOT_AVAILABLE` if the fixed-path receipt is missing; `OBSERVED`
   only means metadata was read, **not** that the receipt is fresh, valid for
   all 17 stages, or from the deployed candidate SHA. Do not treat an
   `e2e_status=PASS` field as a demo GO verdict. Run the independent
   offline readiness gate and inspect the actual receipt under authorized
   sandbox procedures.
6. Record the installed SHA, approval, command and receipt URLs, UTC
   timestamps, and rollback result. If unexpected behavior occurs, stop the
   bridge and restore the previously approved pinned agent; do not attempt
   unreviewed retries or LIVE actions.

**Promotion state at publication:** code and CI PASS; Debian installation
NOT_TESTED; runtime ACME receipt NOT_TESTED; browser demo NOT_TESTED.
