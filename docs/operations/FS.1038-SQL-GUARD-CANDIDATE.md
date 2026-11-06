# FS.1038 — Candidate SQL guard

The production `portal.explorer_api._safe_query` currently permits PostgreSQL `SELECT ... INTO` (FS.1035 FAIL). The deployed explorer source is not yet tracked on this branch.

This change provides an **isolated candidate helper** `portal.sql_readonly_guard.validate_select` and a stdlib-only test harness. **It is not wired into the production explorer** and cannot remediate production until the exact deployed explorer source is reconciled and reviewed.

The helper rejects `INTO`, comments, multiple statements, locking clauses and selected dangerous functions. It deliberately rejects some harmless expressions (e.g. a string containing INTO), preferring false positives to false negatives. **Regex is not a SQL parser**: this helper is only a narrow regression gate, not a complete SQL security boundary. The final implementation should prefer fixed catalog/preview endpoints or a PostgreSQL-aware parser/allowlist, combined with read-only DB roles and transaction enforcement.

Qualification: `bash scripts/fs/FS.1038-sql-guard-candidate-qualify.sh`. No SQL or network I/O. FS.1035 remains a release blocker pending deployed-module reconciliation, negative testing and role checks.
