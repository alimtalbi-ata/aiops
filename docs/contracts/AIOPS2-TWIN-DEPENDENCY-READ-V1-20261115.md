# AIOPS2 Twin dependency read v1 — qualification contract

Status: **DEMO_FIXTURE ONLY / LIVE NO-GO**. Owner: 3/5. Scope: read-only SAN → STORAGE → SERVICE (Payments).

The implementation is `scripts/aiops2_twin_dependency_read.py` and the isolated tests are `tests/test_aiops2_twin_dependency_read.py`. The output schema identifier is `aiops2.twin-dependency-read.v1`. Input nodes carry `id`, `kind`, `tenant_id`; edges carry `from`, `to`, `tenant_id`, `authority`, `source_ref`, `observed_at`, `attested`. The caller supplies `tenant_id`, `as_of`, and a maximum age in seconds (default 900).

This function does not authenticate the caller, validate a signed CMDB receipt, or contact GLPI. `attested: true` is **fixture-supplied**, not independently verified. Thus `SOURCED` means **syntactically source-backed within a synthetic fixture only**. Never promote it to LIVE evidence. The output fixes `mode: DEMO_FIXTURE`, `runtime_attested: false`, and `live_remediation_authorized: false`.

An edge becomes `UNKNOWN` if direction, authority, source reference, attestation, or freshness is insufficient. Invalid tenant identity, cross-tenant nodes/edges, missing endpoints, duplicates, and arbitrary edge fields are rejected. Freshness requires a timezone-aware timestamp with `0 <= as_of - observed_at <= max_age_seconds`. The current output does **not** establish incident causality, an actual Payments impact, a verified GLPI authority, or a cryptographically authenticated provenance chain.

## Dependency and acceptance gate

The integration candidate is [PR #713](https://github.com/alimtalbi-ata/aiops/pull/713); this contract is proposed separately in [PR #715](https://github.com/alimtalbi-ata/aiops/pull/715). Checkmk/Prometheus/Grafana ingestion and correlation remain separate versioned contracts: do not conflate a synthetic event source ID with an authenticated upstream identity. Cross-source deduplication must preserve raw event references and distinguish temporal coincidence from proved dependency/causality.

Before LIVE, independently attest tenant/actor authorization, GLPI source identity and snapshot version, a trustworthy observed timestamp and ingestion time, explicit TTL, authoritative CI-to-service mappings, and the source-specific signal contract. Missing proof must remain `UNKNOWN`; Policy/HITL must fail closed. No arbitrary queries, network grants, SQL, additional cron, or runtime activation are authorized by this document.

Offline test command (execution not implied): `python -m pytest -q tests/test_aiops2_twin_dependency_read.py`. The rollback for this additive document is its removal from the dedicated PR; the runtime is unchanged.
