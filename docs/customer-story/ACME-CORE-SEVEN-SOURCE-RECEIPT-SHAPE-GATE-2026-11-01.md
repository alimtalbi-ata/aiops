# ACME/Twin — Core #291 seven-source informational receipt shape gate

**2026-11-01 · P1 · SOURCE_ONLY / SYNTHETIC / RELEASE_STABLE=NO_GO.** This is an ACME-owned *offline consumer compatibility and refusal test*, not a second Core adapter, a receipt issuer, an authenticated readback, or a deployment plan. The sole architect integration branch is not edited by this PR.

## Source-of-truth and domains

The pinned SAN-A → Pure01 → PAY01 → OraclePay → Payments replay remains seed `20261018`, seven events, graph SQL 005 Git blob `67f0124a2c3b450e5249165e719a5d943fdd7237`, 18 CI/17 edges, path edges `ACME-E08,E06,E04,E02`, and replay JSON SHA256 `bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8`. The existing three-domain ACME fixture receipt SHA256 is `ed53b7b254b80e01b6ee87ad6b2949dfb3f93bb8e4904f48e0b90e75cb8ad4e7`.

Core owner [#291](https://github.com/alimtalbi-ata/aiops/pull/291) defines informational `aiops.core-canonical-seven-source-receipt.v1` and a non-portable receipt digest over sorted compact ASCII JSON `{"schema":"aiops.core-canonical-seven-receipt-hash.v1","event":receipt_without_receipt_sha256}`. The Core source proof uses its *separate* `aiops.core-canonical-seven-transport-proof.v1` domain. Core payload `aiops.core-source-event-payload.v1` and Core full run event `aiops.core-full-run-event.v1` are distinct from all three ACME fixture SHA256 domains. A digest is **not** a signature, and a claimed `TLS_AUTHENTICATED_NONPORTABLE` string is **not** independently observed TLS.

`tools/acme_synthetic_core_source_receipt_gate.py` compares an optional caller-supplied **TEST_ONLY** Core-style shape to the seven pinned ACME source IDs. It enforces seven ordered, unique source events; distinct digest domains; no ACME hash masquerading as Core; explicit test-only actor/tenant fences; exact informational fields; no ALLOW/portable signature; digest integrity; bounded observed/known/expiry times; selected source-event/payload binding; no duplicate test Evidence IDs; and no invented revocation field. The offline comparator cannot authenticate origin, TLS, PG16, actor, tenant, GLPI human permissions, actual Core hashes, source proof or revocation. In particular it **cannot authenticate a swapped pair of opaque Core hash-shaped strings**; that requires an independent Core readback.

The only allowed outcomes are `UNAVAILABLE` with `NOT_SUPPLIED` or `PASS_UNTRUSTED_TEST_INPUT_ONLY`, or a fail-closed `ValueError`. The successful shape comparison **does not** yield a verified Core receipt. Output keeps `tenant_id`, `actor_subject`, `incident_id`, `run_id`, `glpi_ticket_id` and HITL null; `evidence_ids=[]`; `observed_impact=UNKNOWN`; `priority_confirmed=UNKNOWN`; **15 ITIL stages and six checkpoints `NOT_EXECUTED`**. The test suite uses conspicuous `TEST_ONLY_*` placeholders and hash-shaped dummy values; no runtime ID or Evidence is created.

## Qualification and runtime boundary

Existing shared Quality discovery runs `tests/test_acme_san_payments_fixture_contract.py`, now including seventeen new adversarial tests. No workflow is modified.

```bash
python -m unittest discover -s tests -p 'test_acme_san_payments_fixture_contract.py' -v
python -m unittest discover -s tests -p 'test_acme_synthetic_incident_catalog.py' -v
python -m unittest discover -s tests -p 'test_find_acme_demo_run.py' -v
python -m unittest discover -s tests -p 'test_acme_fixture_override_types.py' -v
python tools/acme_synthetic_core_source_receipt_gate.py
```

Core/identity must supply a **separately authenticated, actor+tenant-authorized, fresh and revocation-checked PG16 readback** binding the exact seven ACME events to the same Incident/Run, with provenance and source/evidence hashes. Native GLPI human `ticket:read` and HITL remain separate authorities. The current informational Core receipt, even from disposable PG16 tests, is not sufficient to promote the journey. No ticket, model output, effect or verification receipt is fabricated.

The 2026-11-01 host inventory is a **GitHub-reported observation**, not a live Docker inspection: 61 containers, 53 running/8 exited, and a separate report collected at 12:39:01 UTC. Host image digests, compose labels, ports, volumes, DB ownership, traffic and backups remain **UNKNOWN** here. A single healthy DEV stack and a single canonical Portal TCP **7777** are the target; **17777 is not 7777** and neither port's current host binding is attested by this ACME test. No new persistent container, second portal, Compose change, SSH, host access, DB/volume deletion or LIVE action is authorized.

## Handoff / rollback

Only `tools/acme_synthetic_core_source_receipt_gate.py`, `tests/test_acme_san_payments_fixture_contract.py` and this ACME customer-story document are changed. Base must be re-read from sole Draft #234 immediately before integration. Source branch Quality exact-head results, job logs and artifact checksum must be reported separately from any Debian runtime claim. Revert the focused ACME commits in reverse order; never revert Core audit 013/014, touch `deploy/aiops2-stable`, merge main or mutate the architect candidate. The architect alone integrates selected reviewed blobs.
