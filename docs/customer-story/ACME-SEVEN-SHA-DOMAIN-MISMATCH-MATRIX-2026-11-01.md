# ACME SAN→Payments — seven-event SHA-domain mismatch matrix (2026-11-01)

**Status:** P1 offline SYNTHETIC negative contract. No Core readback or runtime authority. This ACME-owned fixture is not a second Incident/Run/Evidence store and must never be posted to Core or GLPI.

## Sources and immutable scope

- Single integration candidate: Draft #234, starting base \`8b1e121cbd7123d95786133c4cf579030d1bf052\` (refresh before promotion). Main was \`ae7c3e5102b99a66bd7806d602146f1309a9749d\`.
- ACME seed \`20261018\`, graph migration 005 blob \`67f0124a2c3b450e5249165e719a5d943fdd7237\`, seven pinned events and canonical replay SHA256 \`bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8\`.
- Reuses \`tools/acme_synthetic_three_domain_receipt.py\` and the pinned 7,610-byte source JSON, never a parallel generator.
- Core owner source #291: \`app/core/actor_canonical_seven_source.py\` at \`5514ce77728bfd7bf0ce6a1ccf3a6b9a2a9c946d\`; schema \`aiops.core-canonical-seven-source-receipt.v1\`. This schema describes an informational TLS-source preflight receipt, **not** native GLPI human authorization or a portable signature.

## Hash mapping and negative proof

\`tools/acme_synthetic_sha_domain_mismatch_matrix.py --emit\` deterministically outputs \`ACME-SYNTHETIC-SEVEN-SHA-DOMAIN-MISMATCH-MATRIX-2026-11-01.json\`. The seven rows carry the exact source IDs, ACME canonical full-event SHA256, ACME canonical payload SHA256, and a *proposed* Core schema-wrapped payload SHA256. These are three independent local domains; the Core PG16 runtime payload and full-run-event hashes are **null**. Core hashes depend on source-authenticated persisted payload, tenant, Incident/Run, sequence, evidence and timestamps. Do not compare hashes as if they had the same preimage.

The machine-readable negative fixture keeps actor/issuer, tenant, Incident, Run, GLPI ticket/entity/instance, HITL, Evidence, freshness, revocation and TLS readback UNKNOWN/UNAVAILABLE. Tests reject forged identities, foreign partitions, reordered/duplicate events, swapped hashes, forged Core hashes, fake freshness/revocation, altered seed/graph and purported receipts. Matching offline hashes do not grant identity or ticket access.

\`\`\`bash
python -m tools.acme_synthetic_sha_domain_mismatch_matrix --check
python -m tools.acme_synthetic_sha_domain_mismatch_matrix --emit
python -m unittest discover -s tests -p 'test_acme_synthetic_incident_catalog.py' -v
\`\`\`

The **15 ITIL stages and six checkpoints remain NOT_EXECUTED**. No GLPI write, model output, Policy/HITL approval, simulator effect, observed HIGH impact or P1 authority is implied. The SAN-A → Pure01 → PAY01 → OraclePay → Payments reverse-Twin path is a candidate dependency chain, not a verified outage.

## Owner dependency / rollback

Core/identity must supply an **independently authenticated and actor+tenant-authorized** disposable PG16 seven-event readback, source hashes over the actual persisted payload and full run-event domains, audit/freshness/revocation, and native GLPI human rights. Only then may an independent adapter evaluate cross-domain mapping. This offline fixture must not promote IDs or statuses. Revert only the focused ACME source commit; do not touch Draft #234, immutable Core audit 013/014, Debian stack or volumes. \`RELEASE_STABLE=NO_GO\`.

SRV-DEB-05 consolidation is architect-owned: one existing DEV stack, desired portal host TCP **7777** NOT_VERIFIED, distinct from 17777. No SSH, Docker, host, deployment, real GLPI writes or LIVE in this work.
