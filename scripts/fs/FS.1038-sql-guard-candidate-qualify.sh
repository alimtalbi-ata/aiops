#!/usr/bin/env bash
# No production calls, network, SQL connections, or filesystem writes.
set -euo pipefail
cd "${1:-.}"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=app python3 - <<'PY'
from portal.sql_readonly_guard import validate_select
tests = [
 ("basic", "SELECT 1", True),
 ("table", "SELECT id FROM public.example LIMIT 2", True),
 ("insert", "INSERT INTO example VALUES (1)", False),
 ("update", "UPDATE example SET id=1", False),
 ("delete", "DELETE FROM example", False),
 ("drop", "DROP TABLE example", False),
 ("truncate", "TRUNCATE example", False),
 ("multiple", "SELECT 1; DELETE FROM example", False),
 ("comment", "SELECT 1 /*x*/", False),
 ("cte_write", "WITH x AS (DELETE FROM example RETURNING id) SELECT * FROM x", False),
 ("select_into_temp", "SELECT 1 INTO TEMP TABLE example", False),
 ("select_into", "SELECT id INTO example FROM source", False),
 ("select_into_literal", "SELECT 'INTO' AS word", False),
 ("for_update", "SELECT * FROM example FOR UPDATE", False),
 ("for_share", "SELECT * FROM example FOR SHARE", False),
 ("advisory", "SELECT pg_advisory_lock(1)", False),
 ("sleep", "SELECT pg_sleep(1)", False),
 ("dblink", "SELECT dblink('x','y')", False),
 ("select_null", "SELECT NULL", True),
]
failures = 0
for name, sql, expected in tests:
    try:
        validate_select(sql)
        actual = True
    except ValueError:
        actual = False
    ok = actual == expected
    print(f"CASE={name} RESULT={'PASS' if ok else 'FAIL'}")
    failures += not ok
print(f"FS1038_CASES={len(tests)} FAILURES={failures}")
print("FS1038_CANDIDATE=" + ("PASS" if not failures else "FAIL"))
raise SystemExit(bool(failures))
PY
