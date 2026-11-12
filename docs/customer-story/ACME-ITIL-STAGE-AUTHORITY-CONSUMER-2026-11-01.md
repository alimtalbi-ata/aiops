# ACME — 15-stage ITIL receipt consumer (2026-11-01)

**SYNTHETIC / OFFLINE ONLY — RELEASE_STABLE=NO_GO.**

One pinned Golden Payments replay (seed 20261018, migration 005 graph) maps seven local source events into 15 planned ITIL stages and six runtime checkpoints. The source event SHA256, local payload SHA256 and proposed Core payload SHA256 are three distinct LOCAL domains. Core PG16 full-event/payload equality is UNKNOWN, not inferred.

The new `tools/acme_synthetic_itil_stage_authority_consumer.py` composes existing `acme_synthetic_itil_replay_verifier.py` and `acme_synthetic_core_readback_unknown_gate.py`; it does not introduce another Incident/Run store. The machine fixture `ACME-SYNTHETIC-ITIL-STAGE-AUTHORITY-UNKNOWN-2026-11-01.json` is redacted and deterministic.

## Authority gate

Every stage remains NOT_EXECUTED/UNKNOWN and all six checkpoints remain NOT_EXECUTED unless independent owner services establish (1) actor+tenant authorized Core PG16 seven-event readback with immutable 013/014 audit, freshness and revocation; (2) native GLPI human ticket/entity rights; and (3) immutable Evidence tenant/Run/source binding. This offline consumer deliberately has **no positive VERIFIED path**: a client-supplied signed-looking Core document, GLPI `ALLOW`, Evidence `verified`, hash, ticket, actor, Run, or HITL flag is never accepted as authority. A future Core-owned authenticated adapter must provide those proofs; this fixture must not be extended to trust client JSON flags.

Adversarial regressions reject missing/reordered/foreign seven-event manifests, missing/reordered/forged VERIFIED ITIL stage projections, fabricated checkpoint IDs, changed local hash domains and positive counts. Untrusted Core/GLPI/Evidence-shaped JSON is accepted only for a **redacted negative** read; caller IDs and tokens are not copied into output.

## Reproduction (disposable CI / no network)

~~~bash
python -m unittest discover -s tests -p 'test_acme_san_payments_fixture_contract.py' -v
python -m tools.acme_synthetic_itil_stage_authority_consumer --emit
python -m tools.acme_synthetic_itil_stage_authority_consumer --check
~~~

Input fixture authority is `SYNTHETIC_FIXTURE_ONLY`. The 15 stage statuses, six checkpoints, runtime actor/tenant/Incident/Run/GLPI/Evidence/HITL identities, verified priority, observed impact, SIMULATE and resolution remain unexecuted or UNKNOWN. P1 and HIGH are synthetic candidate/estimate only. No real GLPI write, model output, human ALLOW, host action, new persistent stack, port 7777 verification or LIVE.

**Dependency:** Core/identity, GLPI and Evidence owners must independently authenticate, authorize and attest the same seven source events and one Incident/Run. This source-only contract is not a Debian/PG16 runtime E2E test. Rollback: revert only the focused ACME commit; preserve immutable 013/014 audit and architect candidate #234.
