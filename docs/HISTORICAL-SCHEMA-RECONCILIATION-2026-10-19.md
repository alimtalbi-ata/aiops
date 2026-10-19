# AIOps V1/R33 to V2 Schema Reconciliation — 2026-10-19

**Author:** Abdelhalim Talbi  
**Repository:** https://github.com/alimtalbi-ata/aiops  
**Work branch:** `feature/r33-schema-reconciliation-2026-10-19`  
**Status:** Inventory comparison recorded; column-level compatibility and data migration are not qualified.

## 1. Evidence recorded from SRV-DEB-05

The operator supplied the following read-only inventory results:

| Source | Inventory result |
|---|---:|
| Current V2 database `aiops2` | 8 application tables |
| Current V1 database `aiops` | 175 tables across `aiops` and `n8n` schemas |
| R33 historical custom-format dump | Catalogue read succeeded; 1,414 TOC entries reported |
| R33 application schema | 23 table names listed in `r33-aiops-tables.txt` |
| Current exports | Four SQL exports passed gzip integrity checks and SHA-256 manifest verification |

The 175 V1 count includes n8n tables and must not be compared as if all were AIOps business tables. The R33 table list is a selected application-table inventory, not the complete 330-table catalogue. R33 reports 330 table objects and 165 TABLE DATA entries in the custom dump catalogue.

## 2. Current V2 canonical table set

The current `aiops2` inventory reports these eight tables:

- `decisions`
- `events`
- `evidence`
- `incident_submissions`
- `outbox`
- `receipts`
- `remediations`
- `runs`

These are the compact transactional foundation. The inventory alone does not prove that all required workflows are implemented end-to-end.

## 3. Historical capability candidates

The selected R33 list includes:

- Incident lifecycle/correlation: `incidents`, `incident_episodes`, `incident_episode_members`, `incident_relations`, `incident_state_history`, `event_dedup`, `incident_replays`.
- CMDB: `cmdb_objects`, `cmdb_relations`.
- Audit/activity: `audit_events`, `live_activity_events`.
- Knowledge/RAG: `knowledge_documents`, `knowledge_chunks`.
- Remediation: `remediation_runs`.
- Validation/learning/measurement: `runtime_validation_runs`, `learning_candidates`, `value_kpi_daily`, `benchmark_runs`.
- Campaigns: `campaign_batches`, `campaign_batch_items`.
- GLPI bridges: `glpi_conversation_followups`, `glpi_shadow_tickets`, `glpi_ticket_relations`.

These are reuse candidates, not an instruction to copy legacy tables into V2. First inspect the actual DDL, constraints, row counts, data provenance, API consumers and service ownership.

## 4. Reconciliation utility

`tools/schema_reconcile.py` is an offline utility that accepts:
- an R33 table-name list, one name per line;
- a V1 inventory in `schema|table` format;
- a V2 inventory in `schema|table` format.

It emits JSON and Markdown reports classifying name overlap. It does not connect to PostgreSQL or modify any database. Name matching is explicitly not treated as schema or semantic compatibility.

Example:

```bash
python3 tools/schema_reconcile.py \
  --legacy /path/to/r33-aiops-tables.txt \
  --v1 /path/to/aiops-v1-tables.txt \
  --v2 /path/to/aiops2-tables.txt \
  --out /path/to/schema-overlap
```

The inventory files contain no production rows or credentials and should be generated from read-only catalog queries.

## 5. Migration principles

1. Keep V2 as the canonical writer for Run, Event, Evidence, Decision and Remediation state.
2. Do not point V1 and V2 writers at the same logical records without an explicit ownership and consistency contract.
3. Prefer a versioned read adapter for legacy CMDB/incident/knowledge data before considering migration.
4. Preserve source IDs, original timestamps, provenance and source-system identity when mapping historical records.
5. Use idempotent batches, dry-run counts, checkpoints, reconciliation totals and an auditable rollback plan for any future migration.
6. Never restore R33 over the current V2 database.
7. Preserve the PC11K5 claim → fencing/ownership → preconditions → effect → evidence → reconciliation invariant.
8. DEMO/REPLAY/SIMULATION must remain separate from LIVE execution.

## 6. Qualification status

| Gate | Status |
|---|---|
| Current database catalog inventory | PASS (operator-reported output) |
| R33 custom dump catalogue listing | PASS |
| Four current SQL gzip archives and SHA-256 checks | PASS |
| Name-based comparison utility added | Implemented in this branch |
| Utility unit tests | Added; execution result pending |
| Column/type/key/constraint comparison | Pending |
| Historical row-count and data-quality comparison | Pending |
| Isolated restore rehearsal | Pending |
| Application contract and end-to-end tests | Pending |
| Production deployment qualification | Not run |

No production database, container, workflow, or PC11K5 behavior was changed by this repository work.


## 7. Next gate: structural fingerprint (read-only)

The branch now also includes:
- `tools/export_pg_schema_fingerprint.sh`: queries PostgreSQL catalogs only; exports relation names/kinds, column names/types/nullability/identity, constraints and indexes. It deliberately omits table rows, column defaults, comments and application data.
- `tools/compare_pg_schema_fingerprints.py`: compares two exported JSON fingerprints and reports relation/column/constraint/index differences.
- `tests/test_pg_schema_fingerprint.py`: unit tests for structural comparison.
- CI checks Python compilation, the unit tests and Bash syntax.

Run from the checked-out repository on SRV-DEB-05, with permission to inspect the named containers:

```bash
set -eu
umask 077
OUT=/home/aiops/recovery/DB-BACKUP-20261019-193924/validation/schema-comparison
mkdir -p "$OUT"

bash tools/export_pg_schema_fingerprint.sh \
  aiops_v1_postgres aiops "$OUT/v1-schema-fingerprint.json"

bash tools/export_pg_schema_fingerprint.sh \
  aiops2_postgres aiops2 "$OUT/aiops2-schema-fingerprint.json"

python3 tools/compare_pg_schema_fingerprints.py \
  "$OUT/v1-schema-fingerprint.json" \
  "$OUT/aiops2-schema-fingerprint.json" \
  --out "$OUT/v1-vs-aiops2-structural-diff.json"

sha256sum "$OUT"/*schema-fingerprint.json "$OUT"/*structural-diff.json \
  > "$OUT/structural-fingerprint-SHA256SUMS"
```

This operation is intended to be read-only. It executes catalog SELECT queries and writes local JSON artifacts; it does not run DDL, restore a dump, alter data, or restart containers. Check that the container names match the current deployment before running. The V1 fingerprint includes the `n8n` schema if it is in that database; filter it out for business-only interpretation rather than counting it as AIOps functionality.

**Important:** structural equality is not data equivalence or migration approval. Before any migration proposal, inspect foreign-key relationships and row counts separately, then run a restore rehearsal against a disposable database. Do not upload fingerprints if schema identifiers are considered sensitive by the environment owner.
