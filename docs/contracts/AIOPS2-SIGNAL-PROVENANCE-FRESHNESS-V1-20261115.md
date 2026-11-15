# AIOPS2 signal provenance and freshness — read-only contract v1

Status: **PROPOSED / DEMO fixtures only / LIVE NO-GO**. Owner: role 3/5. This is a specification, not an installed adapter, authenticated telemetry or CMDB attestation. No network access, SQL or writes are authorized.

## Envelope `aiops2.signal-envelope.v1`

Required fields: `schema_version`, `mode` (`DEMO` or `REPLAY` in fixture tests), `tenant_id`, `source_kind` (Checkmk, Prometheus, Grafana), `source_instance_id`, `source_event_id`, `ci_ref`, `observed_at` (UTC RFC3339), `received_at` (UTC RFC3339), `signal_kind`, `severity`, `source_ref`, `identity_status` (`VERIFIED` or `UNKNOWN`), `freshness_status` (`FRESH`, `STALE`, `UNKNOWN`), `evidence_status` (`SOURCED` or `UNKNOWN`). A value asserted by a fixture does not establish verified LIVE identity.

Optional metric sample: `value` (finite numeric), `unit` (explicit), `window_seconds` (positive), `metric_name`, `sample_timestamp`. A missing unit/window/timestamp or non-finite value MUST yield UNKNOWN, never a fabricated zero. A Grafana panel reference is not itself a Prometheus measurement.

Freshness is computed against a caller-supplied deterministic `as_of` and explicit maximum age; missing, unparsable, future-dated or untrusted timestamps yield UNKNOWN. Age exceeding the configured maximum yields STALE. Do not use wall-clock time implicitly in fixture tests.

## Deduplication and correlation

Deduplication key: `(tenant_id, source_kind, source_instance_id, source_event_id)`. Identical repeats may collapse with an audit count; conflicting payloads for the same key MUST be rejected or quarantined, not silently overwritten. Cross-source signals do not deduplicate solely on CI, severity or timestamps. Correlation may group signals by tenant, qualified CI mapping and bounded event window; it MUST NOT infer root cause, incident priority or impact from mere temporal proximity. Unqualified mapping yields UNKNOWN. No cross-tenant grouping.

## Twin projection `aiops2.twin-dependency-read.v1`

SAN → storage → Payments is a **hypothesis** until each directed edge has an authoritative CMDB source reference, tenant match, observed timestamp, freshness decision and independently verified provenance. GLPI/CMDB is authoritative; Twin is a derived read model. Missing edge, stale evidence, conflicting direction or unauthenticated provenance => UNKNOWN, never a positive Payments impact. DEMO fixture `attested=true` is a declared fixture attribute, not GLPI attestation.

## Negative qualification matrix (fixtures only)

1. Missing tenant, source instance or source event ID => reject.
2. Same ID with contradictory payload => reject; different sources with same event ID remain distinct.
3. Cross-tenant signal or dependency => reject.
4. Missing, invalid, future or untrusted timestamp => freshness UNKNOWN.
5. Metric without explicit unit/window/sample timestamp, NaN or infinity => evidence UNKNOWN.
6. Missing SAN→storage or storage→Payments edge => impact UNKNOWN.
7. Grafana panel URL without measured sample => metric UNKNOWN.
8. LIVE mode without authenticated server-side source identity and tenant ACL => fail closed.
9. No synthetic fixture may be promoted as proof of LIVE connectivity or source authenticity.

## Integration and rollback

Related drafts: #713 (convergence), #715 (Twin read contract), #723 (isolated regression tests). Implement/test this contract on an isolated branch only after checking current code and ownership; do not overwrite these PRs. CI for this specification is UNKNOWN until a run on its exact SHA is inspected. No runtime deployment or operational rollback applies; revert the documentation commit to withdraw the proposal. Policy/HITL remains fail-closed.
