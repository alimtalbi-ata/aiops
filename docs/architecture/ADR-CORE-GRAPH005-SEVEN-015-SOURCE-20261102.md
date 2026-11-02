# ADR — Core graph-005 exact seven-source synthetic readback (2026-11-02)

Status: **SOURCE_ONLY / CI_ONLY / RELEASE_STABLE=NO_GO**. Scope: Core-owned API, SQL readback, disposable PG16 tests and dedicated workflow. No migration 016 and no changes to ACME graph-005 fixture, Worker, Portal, shared Quality, candidate or Debian.

## Blocker and bounded change

The existing Core 015 synthetic writer accepted only numeric `SYN-EVT-01..07` with `INGEST/SYNTHETIC_SOURCE_EVENT`, while ACME graph-005 pins seven `SYN-EVT-<20 uppercase hex>` IDs and `SOURCE/OBSERVED`. No mapping or event equivalence can be inferred. The new Core `/api/runs/{rid}/events` SOURCE allowance is **restricted to a synthetic DEMO Incident/Run** with tenant/Incident/Run-matching payload, exact 20-hex event key, one Evidence reference, actor and distinct source issuers, version fence and idempotent replay. All other unknown stages remain 422. This internal bearer **does not authenticate a human actor**.

`read_graph005_core_written_seven` queries one Core PostgreSQL transaction in read-only mode, checks the synthetic grant and revocation/expiry, five tenant-resource ownership rows, exact seven run_events and Evidence, source/actor issuer separation, freshness, event ordering and both Core hash domains. It additionally checks a **trusted-listener-pinned** graph Git blob and seven triples (event ID, ACME fixture full SHA256, ACME fixture payload SHA256). Those trusted triples are never accepted from the HTTP request. `dispatch_graph005_core_written_seven` binds this to the existing disposable TLS/Basic listener. A JSON receipt, a Basic credential, an internal bearer and a pinned fixture are not portable IdP/GLPI authority.

The PG16 test reads the unmodified ACME pinned negative contract and regenerates its source IDs/hashes from the pinned synthetic replay; persists seven Evidence and writes exactly seven events via the real Core ASGI endpoint on **one** synthetic Incident/Run; tests independently authenticated HTTPS positive and seven foreign/revoked/expired negatives plus stale and hash mismatch; compares full/payload domains, 013/014 audit before/after and native PG16 `pg_dump` / `pg_restore --single-transaction`. The disposable migration chain is 001/004/009–015. No database host SQL, no DOWN/DROP of a populated environment. Disposable test DB cleanup is not an operational rollback.

## Receipt contract and limits

`core-graph005-seven-015.json` has source head SHA, seven exact source IDs, graph version, ACME fixture hashes, **separately recomputed Core PG16 payload/full-event SHA256**, seven negative UNKNOWN results, immutable 013/014 counts, native DR result, canonical receipt SHA256 and redacted actor hash. It explicitly emits `decision=UNKNOWN`, `link_status=UNKNOWN`, `human_glpi_attested=false`, `portable_signature=NONE`, `acme_full_event_equivalence=NOT_VERIFIED` and `release_stable=NO_GO`. ACME may consume the IDs/hashes as **synthetic source evidence**, not human authorization or graph equivalence.

The existing graph-005 source hashes are local fixture hashes; they are **not** the Core domain hashes. This test cannot prove real source authentication, real IdP grants, GLPI READMY rights, CMDB provenance, external TLS, portal consumption or Debian deployment. Preserve UNKNOWN for all those gates. A successful disposable CI does not qualify host E2E.

Rollback: forward-revert only this focused Core code/test/workflow/ADR delta; retain installed 015, immutable 013/014 audit, and all host DB/volumes. The architect alone selectively integrates after exact-head CI and #186 review.
