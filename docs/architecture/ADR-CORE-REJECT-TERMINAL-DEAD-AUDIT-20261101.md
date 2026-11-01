# ADR — Core atomic terminal DEAD for exhausted REJECT leases (2026-11-01)

**Status:** proposed, source Draft only; architect is sole integrator. No LIVE,
no GLPI write, no new persistent Debian stack or Portal, no Docker socket/SSH.
**Baseline:** sole integration Draft #234 at
`b39fa255d21788978694004be8c851bb271931ef`,
main `ae7c3e5102b99a66bd7806d602146f1309a9749d`.
Worker #292 demonstrates two expired REJECT leases at 8 attempts remaining
`LEASED` without a Core DEAD handler. Worker MUST NOT inject SQL DEAD.

## Core-owned wire

`POST /api/tenants/{tenant_id}/hitl/reject-delivery/{event_id}/dead`
requires service Bearer with tenant ACL, `hitl:reject:deliver` AND the
additional `hitl:reject:terminal` permission. JSON body is exactly the
existing eight-field ACK wire:
`owner,run_id,proposal_id,proposal_hash,proposal_revision,lease_token,
execution_allowed=false,effect_allowed=false`.
The authenticated service actor must exactly equal `owner`.
No caller-provided tenant or Run alone is an authorization fact.

The Core transaction locks the exact REJECT outbox row and joins the exact
proposal hash/revision, approval decision, non-null Incident-backed Run and
independently source-attested tenant ownership. Only `LEASED` with
`attempts>=8`, matching owner/token, expired lease and valid
`REJECTED/REVOKED` source can transition. It updates status to `DEAD`
and inserts one immutable audit row in the **same transaction**.
It returns HTTP 200 `status=DEAD`, `idempotent=false` and receipt SHA256;
a correctly bound replay returns the same receipt SHA256 with
`idempotent=true`. Wrong tenant, actor, hash, revision, token, unexpired
lease, missing source proof or absent event returns 200 `UNKNOWN`
without resource enumeration. Bad bearer 401, missing permissions 403,
DB failure 503; all return `execution_allowed=false,effect_allowed=false`.
No `ALLOW`, approval, effect, Temporal signal, executor or GLPI mutation.

`aiops.core-hitl-reject-terminal-receipt.v1` is a canonical JSON payload
SHA256, not a portable signature or human permission. Its persisted
payload includes tenant, Run, proposal, revision, actor, lease owner,
SHA256 of the strong random lease token (never raw token), attempts,
expired timestamp, DEAD timestamp, source status, and negative-effect
assertions. The HTTP response omits the token and token hash. Replays
compare the stored digest with the canonical payload and refuse mismatches.

## Migration and audit retention

Install `001_schema.sql`, `004_operational_model.sql`,
`009_ai_decision_ledger.sql`, `010_evidence_identity.sql`,
`011_hitl_decision_outbox.sql`, `012_itsm_xref_read.sql`,
`013_actor_delegation_replay_ledger.sql`, then
`014_hitl_reject_terminal_receipts.sql`, on disposable PG16 only.
014 adds one append-only table with an immutable trigger using 012's
existing `prevent_itsm_xref_mutation` function. Reapplication is
idempotent and preserves rows. Do **not** DROP 013 or 014 to revert
application code. On rollback disable/revert the new route and retain
the terminal audit table and its rows. Restore a verified, data-preserving
backup in a separately approved procedure; no in-place downgrade or
production DB operation is authorized by this ADR.

## Test and evidence boundaries

`AIOPS_XREF_CI_DISPOSABLE=1 GITHUB_ACTIONS=true PYTHONPATH=app:tests
python -m unittest discover -s tests -p test_core_hitl_reject_terminal_pg16.py -v`

Dedicated `core-reject-terminal-pg16.yml` runs a disposable PostgreSQL
16 server and native client; checks exact HEAD and **zero SKIP**.
Tests exercise eight real claims, expiry, atomic DEAD, concurrent replay,
stale ACK denial, source-proof removal, cross-tenant and permission
fencing, before-budget denial, immutable audit, migration reapply and
transaction rollback. Synthetic HMAC owner proofs only establish fixture
integrity; they do not attest real human GLPI rights. No Core runtime
on SRV-DEB-05 or port 7777 is modified or observed.

## Worker coordination and Debian consolidation

Worker #292 may consume this route only after architect selectively
integrates it and service credentials receive the explicit terminal
permission. Worker must not change outbox SQL directly or infer terminal
status from attempts. The existing ACK response contract is unchanged.
No additional portal, Compose project, permanent container or host port is
introduced. The single canonical DEV portal remains TCP **7777**
(17777 is not equivalent); actual host PortBindings/health/traffic and
KEEP/MIGRATE/STOP-LATER/UNKNOWN classification require read-only operator
inspection before any deployment. No containers or volumes are stopped
or removed by this source-only change.

**Release:** `actor_authorization=UNKNOWN`,
`link_status=UNKNOWN`, `RELEASE_STABLE=NO_GO`.
