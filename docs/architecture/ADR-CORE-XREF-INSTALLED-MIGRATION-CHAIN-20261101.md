# ADR — Install the real AI/Evidence/HITL/Core xref 009–012 migration chain

**Date:** 2026-11-01. **Status:** Proposed, architect approval required. **Owner:** Core xref 3/5. **Target:** sole architect candidate Draft #234, branch `integration/enterprise-slice-main-20261031-2230`, base `9e8d891ac318d1cc42f3acdf15bdbb320d27f206`. **Release:** NO_GO.

## Decision and Git provenance

Install four byte-identical reviewed SQL Git blobs as actual `db/migrations/` entries, not `tests/fixtures/` copies. This PR is **installation source + qualification contract**, not a DB upgrade or a runtime integration. The existing Core xref API schema remains `aiops.core-itsm-xref-read.v1`, with no new fields. The historical `009_itsm_xref_read.sql` MUST NOT be installed.

| Ordinal | Installed file | Source commit | Git blob SHA-1 |
|---|---|---|---|
| 009 | `009_ai_decision_ledger.sql` | #194 `40d38705cf2bde3be6052340442c117a81908f65` | `bfed91982654b6baf0026408fa5134a22af421bb` |
| 010 | `010_evidence_identity.sql` | #194 same SHA | `1ddafd94639af60ce38b6df0acafd7f63d6b4af2` |
| 011 | `011_hitl_decision_outbox.sql` | #194 same SHA | `b096af57cb19b9618e3d7d4d68a8ef3d56890934` |
| 012 | `012_itsm_xref_read.sql` | #233 `4a22adb19f4d5f1de4a03898cd0908058222d256` | `9408dcf9d92d5bfbdb75968a5a0b0a55f2985457` |

The existing candidate has only installed `000`–`008`. No duplicate ordinals 009–012 are allowed. No change to Portal, Worker, Policy, packaging, shared Core router or architect-owned Quality workflow.

## Qualification and safe execution

`python -m unittest discover -s tests -p test_core_xref_installed_migrations.py -v` runs two stdlib-only provenance/security static checks on any developer machine. The third test requires **GitHub Actions only**, `AIOPS_XREF_CI_DISPOSABLE=1`, and a PostgreSQL 16 service at `127.0.0.1:5432/aiops` under user `aiops`. It creates a new `aiops_xref_installed_ci` DB, refusing a preexisting DB; applies `001→004→009→010→011→012`, checks a complete transaction rollback, two idempotent committed applications, tables and immutable ownership trigger, and destroys the isolated DB. It must never run against production or persistent DBs.

Architect-owned Quality integration proposal (do not edit shared workflow in this owner PR): add a step in the existing PG16 job after dependency installation, **before** the regular Core schema step:

```sh
AIOPS_XREF_CI_DISPOSABLE=1 GITHUB_ACTIONS=true \
  python -m unittest discover -s tests -p 'test_core_xref_installed_migrations.py' -v
```

Ensure the existing PostgreSQL service and `DATABASE_URL` are provided. Static tests also run in that command. The current candidate workflow does **not** run this new suite; green Quality on the PR without the step is **not** proof of the PG16 chain. Architect must re-run on exact integrated HEAD and reconcile with #233 runtime, the final 009–012 hashes, and subsequent HITL/Policy source. Do not claim an actual migration upgrade, data downgrade or rollback on existing data from this disposable DDL test.

## Independent proof / non-enumeration

GLPI is the authority for ticket/entity/CI, Evidence is append-only, Core is the authority for Incident/Run/xref. These SQL tables and their `verified` flags **do not** authenticate GLPI or establish tenant ownership. The #233 runtime design requires a second HMAC ownership manifest bound to the five exact tenant-scoped resources; CI fixtures are synthetic and cannot authorize real `VERIFIED`. An independent trusted GLPI adapter must read back exact ticket, entity, CI and tenant ACL; Core must verify Run→Incident, service token, actor, permission, signed association, source_event_id/association_id and freshness. Missing or tampered proof, stale source or unknown tenant ⇒ `UNKNOWN` without business IDs; 401/403/404/503 remain non-enumerating. Never infer `LINKED` from ticket text containing `RUN-*`. No impact confirmed without sourced telemetry.

## Rollback and unresolved gates

Before merge: revert this single focused source commit; no database has been changed by the PR. In CI: the disposable database is dropped. A persistent upgrade/downgrade and pre-existing-data uniqueness reconciliation require a separate architect-approved migration plan, backup and tests. Source #194 is not a substitute for final integrated HITL/Policy qualification. Block release until exact-head PG16, source-attested GLPI, independent ownership proof, cross-tenant tests and full ITIL vertical are qualified. No production DB, GLPI write, SSH/sudo, merge, main push, deploy or LIVE.
