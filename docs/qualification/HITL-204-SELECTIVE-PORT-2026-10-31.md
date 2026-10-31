# P0 HITL selective port — integration candidate #201 (2026-10-31)

Status: **PROPOSED / NOT INTEGRATED**. Owner: Policy/Worker/outbox/HITL tests. This is a development-only, no-effect handoff, **not** authorization or release evidence.

## Exact source and target (verified at preparation)

- Source #204: `test/hitl-failure-injection-194-20261030@5285aec4359a8132cb6c5801dc8d3a18118930fc`; parent #194 `feat/temporal-hitl-v1@40d38705cf2bde3be6052340442c117a81908f65`; #194 itself targets #193 `feat/glpi-hitl-proposal-fastpath@e8f05d8c50045f4256e89ad0776424f4dad5bb61`. #204 is 77 commits ahead of #194 and changes 11 paths including Core. **Do not cherry-pick the stack or retarget #204.**
- Architect-designated clean-main candidate: #201 `integration/48h-main-based-20261030-1400@fbcb5a35e916199ff82e83193a95d6d93fdacfb3`. This dedicated PR is branched from exactly that SHA; its base is #201, not main.
- Main at preparation: `780a8e03b32e0a3969fc36f6aeee69bacb5b45ab`. #201 vs current main diverges 112 ahead / 3 behind, merge base `27deb9b1a66faf27df8d69b137a63451f7649d80`. Architect alone reconciles/integrates.
- Source #204 exact-head workflows: Quality [41241099554](https://github.com/alimtalbi-ata/aiops/actions/runs/41241099554) 6/6 SUCCESS; V2.8 41241099577, Offline 41241099550, Historical 41241099553 SUCCESS. Source PostgreSQL 16 14/14; DR 32 tables PASS; client fix `7ab131bc0905925e207f92b0552e4beaa9d49f26` ancestor (26 ahead / 0 behind). This **does not** qualify the #201-based port.
- Source artifacts: [PG16 13057039073](https://github.com/alimtalbi-ata/aiops/actions/runs/41241099554/artifacts/13057039073), [DR 13056984498](https://github.com/alimtalbi-ata/aiops/actions/runs/41241099554/artifacts/13056984498), [Temporal/outbox 13057363400](https://github.com/alimtalbi-ata/aiops/actions/runs/41241099554/artifacts/13057363400). Their reported ZIP SHA256 in #204 are respectively `1d7d2b703173fafa49da2b20836a974475495526d45d16535af442626c4a9b76`, `66434a57a3a196640c8b0f62313b1c90fa0db697f35f658831bcfd0274d406a3`, `e0465497a15e4697a1a8677b3362819916eff556f8aae5993b6bae29ee0d7eae`. These are source-PR reported checksums, **not re-hashed here**.

## Port now: independent Policy no-effect response contract

The current #201 Policy `app/policy/main.py` (2.1.0) already distinguishes `SIMULATE` from authorization, and rejects caller-supplied `human_approved=True` as sufficient for a LIVE mutation. The #201 Worker maps DEMO/REPLAY/STORY to OBSERVE and blocks LIVE adapters; neither is a Core HITL ledger.

This PR makes the existing **internal** Policy `evaluate()` verdict explicitly return `execution_allowed=false` and `effect_allowed=false` on every disposition path, including read-only `PASS/ALLOW`, synthetic `PASS/SIMULATE`, UNKNOWN, ESCALATE and BLOCKED. The public `/api/policy/check` endpoint intentionally retains its **strict three-field v2.1 contract** (`state`, `decision`, `reason`), because Core's existing `compare_unbound_policy_values()` rejects additional HTTP fields. A first CI attempt exposed `invalid_policy_http_contract`; the corrected implementation preserves that independent Core fence rather than weakening it. The synthetic `present_simulate_fixture()` now explicitly returns both no-effect flags. These internal/fixture flags are **not** an HTTP authorization or a proof that all Worker/Temporal paths are integrated. Offline decision-matrix, fixture and real-loopback HTTP compatibility tests run in existing CI. An `ALLOW` for read-only observation is **not** an executor grant.

Scope of this PR: `app/policy/main.py`, `app/policy/simulate_fixture.py`, `tests/test_policy_safety.py`, `tests/test_policy_simulate_fixture.py`, `tests/test_policy_real_http_integration.py`, and this HITL qualification note. No Core, Portal, migrations, release manifest, deployment or new workflow.

## Deferred: parent-dependent Worker/outbox/Temporal chain

| Slice from #204 | Dependency and disposition |
|---|---|
| `app/worker/main.py`, `app/worker/workflow.py` | **DEFER**. Current #201 Worker is the 102-line legacy `IncidentWorkflow`; source #204 Worker is ~740 lines with Core proposal/claim/ACK calls. Requires approved Core API contracts and schema chain. Do not copy an alternate workflow. |
| `app/core/main.py` in #204 | **CORE-OWNED — DO NOT PORT HERE.** Core team must reconcile endpoints, tenant fencing, approval transaction, lease token and ACK receipt against the canonical Run/Incident ledger. |
| `tests/test_hitl_*failure_injection.py`, `tests/test_hitl_pg16_outbox_integration.py` | **DEFER executable port** until Core dependencies exist. Test fixtures are synthetic and OIDC is stubbed. Run PostgreSQL 16 `SKIP LOCKED` concurrency, lease expiry, stale/duplicate ACK, lost ACK, retry/dead-letter only after complete schema/API integration. |
| `tests/hitl_outbox_temporal_disposable.py`, `tests/hitl_temporal_server_restart_disposable.py` | **DEFER** until approved ephemeral Temporal+Worker+Core job exists on #201. Source observed synthetic REJECT 2/2, zero effect, Worker and Temporal restart; production `IncidentWorkflow` and actual network loss remain NOT_TESTED. |
| `.github/workflows/quality.yml` | **DO NOT REPLACE** the candidate workflow. Core/CI owners should extend it only after package/DB compatibility, keeping existing DR. |

### Migration and API handshake (Core-owned)

The source #204 migration directory contains `009_ai_decision_ledger.sql` (blob `bfed91982654b6baf0026408fa5134a22af421bb`), `010_evidence_identity.sql` (`1ddafd94639af60ce38b6df0acafd7f63d6b4af2`), and `011_hitl_decision_outbox.sql` (`b096af57cb19b9618e3d7d4d68a8ef3d56890934`). The #201 candidate has **none of 009/010/011**. There is **no 012 file in the #204 source migration directory**; its expected filename, owner and contents must be confirmed by Core before claiming a 009–012 chain.

- 009 defines immutable analysis/critique/Policy/proposal/approval/effect ledgers and transition guards; 010 requires evidence source/payload/external-ID uniqueness; 011 creates the FK-bound, leased, at-least-once HITL decision outbox. Importing 011 without 009 and 010 is prohibited.
- Core must provide the exact 012 identity/blob (or state explicitly that 012 is not applicable), ordered migration upgrade + rollback plan, verified schema compatibility, API request/response examples for proposal, OIDC verification, decision commit, claim and ACK, lease/fencing/idempotence and tenant/SoD rules.
- Temporal signals are **notifications only**. No signal, synthetic actor, fixture digest, Policy `PASS`, or boolean human approval creates authority. All synthetic receipts must remain `execution_allowed=false`, `effect_allowed=false`, zero effects. OIDC/MFA real: **NOT_ATTESTED**.
- PG16 source uses `postgres:16-alpine`, Python 3.12 and `psycopg[binary]==3.2.13`; source `pg_restore 16.15` DR stays active. If package install fails on a future target, propose a separately pinned, reproducible Python/psycopg/PG-client alternative with evidence; never remove DR to get green.

## Qualification, rollback and ownership

Commands for this port: `python -m unittest discover -s tests -p test_policy_safety.py -v`; `python -m unittest discover -s tests -p test_policy_simulate_fixture.py -v`; `python -m unittest discover -s tests -p test_simulation_policy_contract.py -v`; with the ephemeral Policy service listening on 127.0.0.1:1813, `python -m unittest discover -s tests -p test_policy_real_http_integration.py -v`. The existing candidate Quality workflow runs all four. New exact-head CI must be checked on the PR head before calling this port PASS; PostgreSQL 16/outbox/Temporal are **NOT_TESTED on this port** until a Core-owned integrated environment exists.

Rollback: revert the targeted Policy/test/doc commits on this dedicated branch (or close the draft PR); no DB migrations, external effects, host access or release state to undo. Integration is architect-owned, never automatic.

**RELEASE_STABLE=NO_GO**. No LIVE remediation, executor, SSH, sudo, Ansible, real GLPI writes, deploy, merge or main push.
