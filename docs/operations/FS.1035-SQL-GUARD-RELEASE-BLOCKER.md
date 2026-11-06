# FS.1035 — SQL read-only guard: blocking finding

Date: 2026-11-06. Scope: production image `aiops2-portal:fs621-explorers-candidate`, **no production changes**.

## Reproduction (no SQL execution)
The function `portal.explorer_api._safe_query("SELECT 1 INTO TEMP TABLE example")` returned normally. The regression harness reports `SQL_GUARD_TESTS_FAILED=1` and `FS1035_GUARD_QUALIFICATION=FAIL`. The other 13 test cases passed. This is a **validator bypass**, not proof that the database user can write.

## Release blocker
Do not configure or activate the database explorers until a corrected validator and least-privilege database credentials have passed qualification. The production module `/app/portal/explorer_api.py` is present in the deployed image but **absent from this Git branch**. Avoid replacing the production portal with the older source tree, which lacks routes and integrations.

## Remediation requirements
- Import/reconcile the **exact deployed** `explorer_api.py` source into version control through a reviewed change, without credentials or runtime env.
- Replace regex-only SQL write filtering with a fail-closed, narrowly scoped query policy; explicitly reject `SELECT ... INTO`, CTE data modification, multiple statements, dangerous functions and other side-effecting expressions. Prefer catalog/preview endpoints and fixed parameterized queries over arbitrary SQL.
- Enforce read-only PostgreSQL roles with `default_transaction_read_only=on` / read-only transactions as defense in depth, with no CREATE/TEMP/EXECUTE-on-unsafe-functions grants. Validate actual permissions separately.
- Extend FS.1035 with bypass cases and run against the **candidate** image; do not test writes against production.
- Review GLPI session-opening POST and Prometheus operation allowlist separately.
- Require explicit production authorization before configuration or rollout.

## Qualification status
FS.1029 PASS (unit); FS.1030 PASS (network); FS.1031–1034 discovery; **FS.1035 FAIL / release blocked**.
