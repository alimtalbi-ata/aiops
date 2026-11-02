# ACME graph-005 Core 015 PG16 CI receipt consumer — 2026-11-02

**Scope:** ACME/Twin-only source integration; synthetic, disposable CI only. This is not an independently authenticated host or human-actor readback.

## Independently produced Core input

Core-owned [exact candidate workflow #41382867559](https://github.com/alimtalbi-ata/aiops/actions/runs/41382867559) at SHA `3d4880256d5ffce0a403565ea12dffef2b0bf8e7` produced [artifact #13114440885](https://github.com/alimtalbi-ata/aiops/actions/runs/41382867559/artifacts/13114440885). Downloaded ZIP SHA256 `e40e0f5e1800e3b6501c7d097c08838f1fac747c5592526498593667e4c3adb0`, CRC PASS. Exact `core-graph005-seven-015.json` bytes SHA256 `bf74927d5cfb847f86b4933ff21d3ebb13684a23335e362b1f3e88923a7c9617`; canonical embedded receipt SHA256 `ceceff9e71ca414f2e5b0d9272408c10a3df7c2e405609d174036d419f989de2`. A verbatim redacted test fixture is pinned in `tests/fixtures/acme_core_graph005_pg16_ci_fixture_v1.json`; its synthetic `TEN/INC/RUN-GRAPH005` scope is not copied to the ACME output.

Run from repository root:

```bash
python tools/acme_graph005_core_ci_consumer.py \
  --core-ci-receipt tests/fixtures/acme_core_graph005_pg16_ci_fixture_v1.json \
  --expected-core-head 3d4880256d5ffce0a403565ea12dffef2b0bf8e7 \
  --expected-receipt-sha256 ceceff9e71ca414f2e5b0d9272408c10a3df7c2e405609d174036d419f989de2 \
  --expected-file-sha256 bf74927d5cfb847f86b4933ff21d3ebb13684a23335e362b1f3e88923a7c9617
python -m unittest discover -s tests -p test_acme_san_payments_fixture_contract.py -v
```

## Bounded contract and refusal

- Seven **exact** graph-005 `SYN-EVT-<20 uppercase hex>` IDs in order, local ACME full/payload fixture SHA256 pinned, distinct Core PG16 full-event/payload SHA256 domains and same disposable Core CI test provenance. A digest matches **bytes**, not an independently authenticated actor or authorization.
- Graph 005 reverse dependency path: `ACME-SAN-FABRIC-A → ACME-STO-PURE01 → ACME-VM-PAY01 → ACME-APP-ORACLEPAY → ACME-SVC-PAYMENTS`; edges `ACME-E08/E06/E04/E02`; 10 CI in **candidate** blast radius, HIGH estimate, no observed Payments outage.
- Core CI artifact reports synthetic single Incident/Run and migration 013/014/015 checks; ACME output deliberately redacts Core synthetic scope and preserves `actor_tenant_acl/freshness/revocation=UNKNOWN`, `core_https_runtime_authentication=NOT_INDEPENDENTLY_ATTESTED`, `GLPI/HITL=UNKNOWN`.
- All 15 ITIL stages and six checkpoints remain `NOT_EXECUTED`, zero `VERIFIED`. A CI artifact has no portable signature and does not prove current host Core readback, human IdP/GLPI READMY, immutable Evidence, TLS external, HITL or LIVE.
- Missing/reordered/foreign IDs, unpinned HEAD/digest, tampered full/payload, invalid source domains, forged GLPI authority, audit mismatch, revoked/expired claims or foreign graph fail closed with no Core hashes copied.
- The next positive gate requires a **fresh independent HTTPS readback** of the same Core Incident/Run under verified source and actor/tenant ACL, expiry/revocation and immutable 013/014, then separate GLPI human/Evidence/HITL gates. Do not reuse a portable CI JSON as that readback.

**Ownership/rollback:** only `tools/acme_*`, `tests/test_acme_*`, `tests/fixtures/acme_*` and `docs/customer-story/ACME-*` changed. Architect alone selectively integrates; forward-revert these ACME commits/files if needed. No candidate/main/stable/host/volume/GLPI/LIVE mutations. `RELEASE_STABLE=NO_GO`.
