# AIOPS2 read-model negative contract matrix v0.1

Status: PROPOSAL ONLY. No existing endpoint is asserted to implement this contract. Parent: `f27ed59f0e47611c6e87ca4554be6f16f4485644`. Companion: `docs/contracts/portal-readmodels-v0-proposal.md`.

## Trust and isolation invariants

- Resolve actor identity, tenant membership and capabilities from the authenticated server session on **every** request; never use browser-provided `actor_id`, `tenant_id`, role or capabilities as authority. Verify the tenant-to-resource mapping **before** fetching any data or exposing its existence.
- Tenant isolation must be enforced in source queries, not only after serialization. Apply row-level and object-level ACLs to list/detail, aggregation, counts, facets, evidence references and cursors. Unauthorized existence must not be observable through response size, counts, error details or source references.
- Require an immutable `(tenant, run_id, mode, incident_id)` association from the authoritative read store for run-scoped evidence and timeline. A missing qualifier is 400; mismatch is 400 only if the tuple can be validated without leaking existence, otherwise tenant-safe 404. Never guess a mode or incident.
- `READY` requires validated schema, complete authorized result, trustworthy source reference and timestamps, and freshness within a documented per-source threshold. Source failure, stale observation or partial inventory cannot become `READY` or an empty successful collection.
- `BLOCKED` represents a known policy/ACL denial, never a transport timeout. 401 and 403 must remain HTTP errors, not HTTP 200 with a cosmetic state. Unknown source => `UNKNOWN`; broken upstream => `ERROR`; cancellation => no response or documented 499 (where supported).
- Host collector output is **not** an authorization or business-health source. Never join raw host inventories into tenant-facing CMDB, incident or dashboard data without independently reviewed ownership mapping and disclosure policy.

## Endpoint-specific contract matrix

| Family | Required scope | Authoritative source / provenance | Failure / freshness condition |
|---|---|---|---|
| Dashboard/health | tenant + dashboard.read | registry + service-specific health read adapters | Missing health sample => UNKNOWN per service, never green from Docker uptime |
| Incidents | tenant + incidents.read | incident store, immutable incident ID | Source unavailable => UNKNOWN; no fabricated empty list |
| Services/CMDB | tenant + cmdb.read + entity mapping | approved CMDB snapshot | Unmapped GLPI entity => BLOCKED, not global fallback |
| NOC | tenant + noc.read | event stream with watermark | Watermark behind SLA => UNKNOWN |
| Twin | tenant + twin.read + explicit mode | immutable Twin snapshot | Missing mode/snapshot => 400/UNKNOWN; no simulation |
| Runs/timeline | tenant + runs.read + verified tuple | run event store + ordered event IDs | Mismatched run/mode/incident => reject before source projection |
| Evidence | tenant + evidence.read + verified tuple | evidence index + content ACL | Missing/forbidden evidence => no raw URI leakage |
| Policy/HITL | tenant + policy.read | immutable decision/audit projection | No approval or policy changes via read adapter |
| Prometheus/Grafana | tenant + observability.read + allowlisted query | metric labels, source timestamp, datasource ID | Unknown tenant label mapping => BLOCKED; no arbitrary PromQL proxy |
| GLPI | tenant + cmdb.read + approved entity mapping | read-only GLPI connector + sync watermark | Mapping missing => BLOCKED; no writes |
| Copilot | tenant + copilot.read + referenced run/incident ACL | saved explanation + cited evidence IDs | Missing provenance => UNKNOWN; no tool execution |

## Pagination and asynchronous consistency

Cursor payload (signed or authenticated-encrypted, never trusted unsigned): `tenant_scope_hash`, `actor_scope_version`, `resource_family`, `filter_hash`, `sort_key`, `snapshot_watermark`, `expires_at`. Reject cross-tenant, filter mismatch, ACL-version mismatch, expiry and tampering with 400/403 according to the approved information-leak policy. Limit 1..100, default 50; enforce stable `(observed_at, immutable_id)` order and bounded snapshot window. Never use offset paging for mutable streams without a snapshot contract.

Propagate cancellation from client to adapter and upstream; set upstream timeout below 5s adapter deadline, bounded retries only when safe, and terminate work on disconnect. A response carries a request generation; client promotion requires exact equality with current generation **and** matching tenant, filter and run tuple. A late success from an earlier generation is discarded and cannot replace an ERROR/UNKNOWN for the current request.

## Executable test cases to implement against actual adapters (NOT_EXECUTED)

| ID | Input / injection | Required assertion |
|---|---|---|
| AUTH-01 | no session | HTTP 401; upstream mock not called |
| AUTH-02 | forged tenant/actor headers | server session wins; no cross-tenant data |
| ACL-03 | actor lacks family capability | HTTP 403, BLOCKED; no upstream call |
| TEN-04 | tenant B requests tenant A ID | tenant-safe 403/404; no counts, existence or source_ref |
| PAGE-05 | tenant B reuses A cursor | reject; zero records |
| PAGE-06 | tampered/expired/filter-mismatched cursor | reject; no fallback to first page |
| RUN-07 | missing run_id/mode/incident_id on run-scoped detail | HTTP 400; no upstream call |
| RUN-08 | valid IDs but mismatched tuple | reject; no evidence or timeline exposure |
| TIME-09 | upstream exceeds deadline | ERROR/UPSTREAM_TIMEOUT; data null |
| CANC-10 | client aborts during fetch | upstream aborted; no response promotion |
| GEN-11 | generation n finishes after n+1 | n discarded, n+1 unchanged |
| FRESH-12 | stale or absent observed_at/source_ref | UNKNOWN; data null |
| PART-13 | partial or malformed source page | UNKNOWN/ERROR; no READY, no invented count |
| DENY-14 | unqualified bootstrap/demo/copilot | 403/BLOCKED, no fallback |
| HOST-15 | Docker healthy but business health missing | business state UNKNOWN, never READY |

## Debian coordinator gate (NOT_INSTALLED)

Before scheduling, run `python3 -m unittest discover -s tests/observability -p 'test_debian_rootless*.py' -v`, verify UID 1001, rootless Docker access, trusted non-symlink path ownership, 0600 output, lock contention, timeout and retention. Inspect a sample JSON for sensitive identifiers and unsafe log fragments; keep unapproved endpoints/logs UNKNOWN. Proposed cron entry **only after review** (replace both absolute paths with reviewed locations):

```cron
*/15 * * * * /usr/bin/timeout -k 5s 120s /usr/bin/python3 /ABSOLUTE/REVIEWED/scripts/observability/debian_rootless_readonly.py
```

Do not install blindly: confirm script CLI, output path environment, lock path and exit codes against the reviewed SHA first. Run under `aiops` (UID 1001), never root. The coordinator owns installation and rollback. No GLPI/DB writes, no LIVE remediation.
