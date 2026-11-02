# ACME/Twin sourced service context — synthetic-only contract

**Scope:** additive offline storyboard projection on the architect's sole Draft #234 candidate. No second CMDB, incident ledger, generator or runtime adapter. No effectful operation.

## Authorities and provenance

- Pinned synthetic graph: `db/migrations/005_seed_acme.sql`, Git blob `67f0124a2c3b450e5249165e719a5d943fdd7237`; 18 nodes, 17 directed consumer-to-dependency edges. The parser fails closed on a changed blob, missing node, altered type or criticality.
- Golden replay: `SCN-GOLDEN-PAYMENT-P1`, seed `20261018`, seven events; the existing replay JSON and `dataset_sha256` are **not changed**. The context is added only to `storyboard_offline()` after strict full-manifest validation.
- The site `PARIS` is a synthetic node property for the five SAN-A→Payments path nodes, **not** a verified datacenter, physical location, tenant or customer record. Service criticality `5` is the seed's ordinal 1–5 value, **not** a contractual SLA or a measured outage.
- The graph path reverses stored edges `ACME-E08,E06,E04,E02` (SAN-A → Pure01 → PAY01 → OraclePay → Payments); `ACME-E01` links Payments to the business node. Reverse-reachable ERP and Payments services are *blast-radius candidates*, not verified affected services. SAN-B redundancy exists, but failover and causality are not verified.
- Priority `P1` is a synthetic candidate from estimated HIGH impact and synthetic CRITICAL urgency. Confirmed priority, actual impact and verified ITIL assignment remain `UNKNOWN`.

## Missing data — never infer

`datacenter_id`, `datacenter_relation`, `service_owner_id`, `service_team_id`, `sla_id`, `ola_id`, `change_id`, `maintenance_actual`, `blast_radius_observed`, `impact_observed`, `itil_priority_confirmed` are all `UNKNOWN`. The Golden catalog's `maintenance_window_synthetic=null` only says no simulated window was configured; it does not prove no actual maintenance. `CHANGE_LOOKUP` at +45s is planned, not a returned change record.

The runtime `tenant_id`, `incident_id`, `run_id`, `ticket_id`, Evidence IDs and all GLPI→Core→Run→Evidence→resolution→reopen checkpoint receipts remain `UNKNOWN` or `NOT_EXECUTED`. Do not turn synthetic event IDs into authenticated Core identities.

## Test and promotion gate

The existing Quality catalog discovery `python -m unittest discover -s tests -p 'test_acme_synthetic_incident_catalog.py' -v` covers five additional tests: pinned node/site/criticality, unknown service governance fields, dependency/blast-radius semantics, forged-manifest rejection and changed-graph rejection. Also execute the existing fixture, override-type and locator suites. No shared workflow edits.

Promote only after exact-head CI logs show `Ran N tests` and `OK`, the canonical replay JSON SHA256 remains `bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8`, and the architect independently reviews the diff. GitHub ZIP digest is not a substitute for replay JSON checksum. Rollback: revert the focused PR's commits; do not modify the pinned 005 SQL or canonical replay.
