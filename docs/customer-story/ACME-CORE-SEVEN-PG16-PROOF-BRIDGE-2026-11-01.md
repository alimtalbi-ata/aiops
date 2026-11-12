# ACME SAN→Payments — Core PG16 seven-event bridge (SYNTHETIC, 2026-11-01)

## Ownership and runnable contract

This ACME-only bridge consumes the **raw shape** of Core's `aiops.core-canonical-seven-source-binding.v1` producer. It does **not** create a Core Incident, Run, Evidence, GLPI ticket or HITL decision. Core owns the disposable PG16 writer, the actor+tenant authorized independent HTTPS/TLS readback and immutable audit 013/014. The existing source `tools/acme_synthetic_pg16_twin_impact_handoff.py` prepares seven Core-domain TEST_ONLY payloads; Core must write exactly these **seven pinned `SYN-EVT-*` IDs**, not `EVT-SOURCE-01..07`, under **one** Core-owned Incident and Run. TEST_ONLY scope is explicitly provided in a disposable test, never inferred or presented as a runtime ID.

```sh
python -m tools.acme_synthetic_pg16_seven_bridge --check
python -m unittest discover -s tests -p 'test_acme_san_payments_fixture_contract.py' -v
```

The new `AcmeCorePg16SevenBridgeTests` class is deliberately inside the existing Quality-discovered fixture test file; no shared workflow changes. The `--core-proof` option accepts a **local untrusted JSON document only** (64 KiB cap, duplicate JSON keys rejected). A structurally consistent proof still returns `CONSISTENT_UNTRUSTED`, never `VERIFIED`. The bridge does not call a network, database, GLPI or LIVE executor.

## Required Core-owned integration boundary

1. Core's disposable PG16 writer must create one synthetic Incident/Run and seven ordered SOURCE/OBSERVED/PASS Run events, with exact ACME source IDs and matching Evidence payloads. The installed Core `run_events.event_key` migration is an independently reported writer blocker: a failing HTTP 500 is **not** acceptable proof of a successful write.
2. An independently authenticated Core source service must read those seven events in one read-only PG16 transaction with actor IdP issuer and source issuer **separately pinned**, tenant/actor grant, linked Incident/Run, source provenance, freshness ≤300 s, revocation and exact full/payload SHA256 domains. The Core producer's receipt alone is not portable authentication; the caller must verify TLS peer, issuer, actor/tenant ACL and 013/014 audit independently.
3. The ACME consumer compares the exact seven IDs, order, CI/action/timestamps, one scope, source payload hashes and Core full-event hashes against the pinned Twin graph 005. Core full-event SHA and ACME full-event SHA are **different serialization domains**; byte equality cannot confer authorization.
4. GLPI native human User/Profile/Entity/Ticket READ/READMY and HITL approval require **separate** independent proofs. Even a valid Core PG16 source readback cannot grant GLPI ALLOW or mark the ITIL replay executed.

## Redacted outcome and rollback

Pinned receipt: `ACME-CORE-SEVEN-PG16-PROOF-BRIDGE-UNKNOWN-2026-11-01.json`, seven `SYN-EVT-*` local SHA triples, SAN Fabric A→Pure01→PAY01→OraclePay→Payments via graph edges ACME-E08/E06/E04/E02, ten CI candidate blast radius, estimated HIGH/P1 candidate only. Core PG16 full/payload hashes, runtime tenant/actor/Incident/Run/GLPI/Evidence IDs and HITL remain null/UNKNOWN. **15/15 ITIL stages and 6/6 checkpoints NOT_EXECUTED**. No observed service impact, no remediation and no Portal route claimed.

Only ACME-owned paths change. Revert the focused source commits in reverse order, rerun exact-head Quality, and leave immutable 013/014 audit, PG16, Docker volumes, host services and sole Draft #234 untouched. Operator-local portal TCP 7777 health is verified; external TLS/SSO/GLPI and portal uniqueness are not. `RELEASE_STABLE=NO_GO`.
