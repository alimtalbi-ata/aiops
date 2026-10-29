# Demo Studio AI Ledger — synthetic evidence reference binding

Owner: NOC/Copilot. Candidate on top of #145 → #149 → #154 → #161; **BLOCKED / NOT_READY_FOR_STABLE**.

## Viewer contract

`GET /api/demo-studio/runs/{rid}/ai-ledger` remains viewer-authenticated using `AIOPS_PORTAL_READ_TOKEN`. The browser must never receive `AIOPS_INTERNAL_TOKEN`. Existing `aiops.demo-ledger-read.v1` response remains backward compatible **only for qualified synthetic Runs**; it now requires a third upstream Core read:

1. `GET /api/runs/{rid}` (internal Bearer, DEMO/REPLAY/STORY, tenant-scope rejection).
2. `GET /api/runs/{rid}/ai-ledger` (internal Bearer, Analysis/Critique/Policy projections, referential claim checks).
3. `GET /api/noc/runs/{rid}/evidence-refs` (internal Bearer, PostgreSQL Run-event/Evidence link qualification, `aiops.core-demo-evidence-refs.v1`).

A valid response additionally contains `evidence_classification: "SYNTHETIC_ONLY"`, `event_link_verified: true` and bounded `evidence_refs[]` with only `evidence_id`, `source`, `payload_sha256`, `known_at`. Every Analysis evidence ID must match exactly the Core resolver IDs. All source metadata is validated; unknown fields, duplicates, missing references, unqualified tenant fields, mismatched Run IDs, unsupported provenance flags, malformed hashes or timestamps fail closed.

**Missing Core endpoint, HTTP 401, invalid or absent source, LIVE Run and tenant-scoped evidence → HTTP 503 `UNKNOWN`, no-store and no private payload.** Viewer missing/invalid Bearer → HTTP 401 before Core I/O. The browser token is never forwarded upstream.

These references prove *internal referential linkage for synthetic records*, **not** source truth, payload rehashing, tenant RBAC, observed SAN/Payments metrics, causal impact, runtime attestation, an Ollama response or Policy SIMULATE execution. `supported=true` is still a recorded Critic claim, not an externally verified business fact.

## Qualification / deployment

`.github/workflows/quality.yml` existing `quality-build-package` runs unit contract tests; `database-migrations` starts actual ephemeral Core/Portal/PostgreSQL 16 and runs `tests/test_demo_ledger_real_http.py` (including missing event and upstream 401). No parallel workflow. A real CI result must be checked on the exact final SHA before PASS is asserted.

The Debian poller watches **only** `deploy/aiops2-stable`. The existing Studio deploy script does not install `app/core/demo_evidence_read.py` or Core route registration, so deploying only the Portal change would deliberately return 503. Schedule 5/5 must assemble and verify both services, release/rollback coverage, auth configuration and post-deploy read-only smoke tests before any stable promotion. No Debian access or `applied.sha` proof is claimed.

NOT_TESTED: Debian, tenant A/B runtime actor ACL, observed SAN CRC/Payments p95, Twin impact, Ollama 4B, Temporal/Policy E2E, browser screenshot/video and rollback.

## Temporal integrity addendum — candidate #167 (2026-10-28)

The Portal independently rejects an Evidence reference whose `known_at`
is timezone-naive or more than five minutes ahead of the Portal clock,
even if an upstream Core response claims `event_link_verified=true`.
The result is HTTP 503 `UNKNOWN`, `no-store`, without exposing IDs,
tokens or private ledger content. The existing viewer-authenticated endpoint
and `aiops.demo-ledger-read.v1` response schema are unchanged.
This is **not** a source/clock attestation or proof of observed metrics.

## Per-Analysis citation fence — 2026-10-29

For each Critique, `evidence_ids` must be a subset of the `evidence_ids` of its **own** referenced Analysis, not merely of the Run-wide union. Even if no `claim_checks` entry claims `supported=true`, a Critique borrowing an Evidence ID from another Analysis fails closed with HTTP 503 `UNKNOWN` and `no-store`. A multi-Analysis ledger with correctly linked Evidence remains readable. This tightens the existing `aiops.demo-ledger-read.v1` contract without changing the response schema or the Core resolver contract. It does **not** establish tenant ACL, source truth or Policy SIMULATE attestation.

## Policy linkage fence — 2026-10-29 01:27 CET

Policy decisions shown in the read-only AI Ledger must have a non-null
`analysis_id` or `critique_id` pointing to records returned **for the same Run**.
If both are present, the Critique must belong to the referenced Analysis.
Duplicate `policy_decision_id` values are rejected. Missing, cross-Run,
cross-Analysis or duplicate links yield 503 `UNKNOWN` with `no-store`,
without exposing internal IDs or credentials. The public
`aiops.demo-ledger-read.v1` JSON schema is unchanged; this is a stricter
fail-closed qualification, not a proof that Policy SIMULATE actually executed.
Unit cases and real ephemeral Core/Portal/PostgreSQL 16 HTTP regression are
added to existing `quality.yml`; results require checking the exact SHA.

## Synthetic Policy disposition fence — 2026-10-29 02:24 CET

The existing viewer-authorized `aiops.demo-ledger-read.v1` projection now
rejects a persisted Policy decision with `ALLOW`, a LIVE effect command
(`EXECUTE`, `REMEDIATE`, etc.), an unknown decision, or an unknown state.
Accepted synthetic read-only dispositions are `SIMULATE`,
`HUMAN_APPROVAL`, `ESCALATE`, and the legacy non-effect `BLOCK`/`OBSERVE`;
states are `PASS`, `BLOCKED`, `UNKNOWN`. This is deliberately fail-closed:
Core Policy emits `ALLOW` only for LIVE, and a DEMO ledger must not present
it as a simulation success. A malformed disposition returns HTTP 503
`{"status":"UNKNOWN","reason":"ledger_unavailable"}` with `no-store`,
without reflecting internal IDs or credentials. Viewer 401-before-I/O,
Core server-side Bearer, evidence bindings and the response JSON schema
are unchanged. Historical unknown dispositions may now be refused; the
release integrator must qualify compatibility, not silently downgrade.
A real Core/Portal/PostgreSQL 16 CI test persists an `ALLOW/PASS` row
for a synthetic Run to verify the refusal. **This does not execute Policy,
attest tenant RBAC, authorize LIVE or prove SAN→Payments causality.**


## Malformed viewer Bearer fence — 2026-10-29 03:22 CET

The viewer-authenticated endpoint rejects non-ASCII Bearer values, values
longer than 256 characters, and values containing whitespace with HTTP 401
`{"status":"UNKNOWN","reason":"unauthorized"}` and `Cache-Control: no-store`,
**before** Core HTTP I/O. In particular, Unicode credentials must not
trigger an uncaught `hmac.compare_digest` exception or a 500. Viewer
configuration failures still return 503; valid viewer credentials remain
separate from the internal Core token. Unit tests assert zero Core requests;
the existing `quality.yml` runs a real ephemeral Portal HTTP regression.
No JSON response schema or endpoint is changed. This is input-hardening,
**not** tenant RBAC, real SAN/Payments evidence, or Debian attestation.

## SIMULATE/PASS requires validated Critique — 2026-10-29

A synthetic Policy row claiming `SIMULATE/PASS` must link to a Critique
in the same Run whose persisted `validated` flag is **true**. A missing
Critique link or a linked Critique with `validated=false` yields HTTP 503
`UNKNOWN` with `no-store`, without leaking IDs or tokens. Merely matching
Analysis/Evidence IDs is insufficient to present a successful simulation.
The `aiops.demo-ledger-read.v1` JSON shape and upstream Core contracts do
not change; previously accepted inconsistent synthetic rows may be refused.
This checks the recorded Critique flag, **not** the actual independence of
review, freshness of observed SAN/Payments metrics, tenant ACL or an E2E
Policy execution. A qualified `SIMULATE/PASS` is still synthetic only.
