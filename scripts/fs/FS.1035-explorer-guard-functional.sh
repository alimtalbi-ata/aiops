#!/usr/bin/env bash
# FS.1035: functional SQL guard tests, static GLPI/Prometheus review.
# No network queries, no SQL connections, no secrets, no production mutations.
set -euo pipefail
echo "FS1035_MODE=NO_IO_GUARD_TESTS"
docker exec aiops2-rebuild-portal python -c '
import ast, inspect, json
from fastapi import HTTPException
import portal.explorer_api as m
print("===== SQL GUARD FUNCTIONAL TESTS =====")
tests=[
 ("select_basic","SELECT 1",True),
 ("select_table","SELECT id FROM public.example LIMIT 2",True),
 ("insert","INSERT INTO public.example VALUES (1)",False),
 ("update","UPDATE public.example SET id=1",False),
 ("delete","DELETE FROM public.example",False),
 ("drop","DROP TABLE public.example",False),
 ("truncate","TRUNCATE public.example",False),
 ("multiple_statements","SELECT 1; DELETE FROM public.example",False),
 ("comment_followed_write","SELECT 1; /*x*/ DROP TABLE public.example",False),
 ("cte_write","WITH x AS (DELETE FROM public.example RETURNING id) SELECT * FROM x",False),
 ("select_into","SELECT 1 INTO TEMP TABLE example",False),
 ("explain_analyze_write","EXPLAIN ANALYZE DELETE FROM public.example",False),
 ("copy_to","COPY public.example TO STDOUT",False),
 ("do_block","DO $$ BEGIN DELETE FROM public.example; END $$",False),
]
failures=0
for name,sql,expected in tests:
 try:
  m._safe_query(sql)
  allowed=True
 except HTTPException:
  allowed=False
 except Exception as e:
  print("TEST=%s STATUS=ERROR TYPE=%s"%(name,type(e).__name__))
  failures+=1
  continue
 result="PASS" if allowed==expected else "FAIL"
 print("TEST=%s EXPECTED=%s ACTUAL=%s RESULT=%s"%(name,"ALLOW" if expected else "DENY","ALLOW" if allowed else "DENY",result))
 if result!="PASS": failures+=1
print("===== GLPI HTTP METHOD STATIC REVIEW =====")
fn=ast.parse(inspect.getsource(m._glpi_inventory))
for n in ast.walk(fn):
 if isinstance(n,ast.Call):
  for kw in n.keywords:
   if kw.arg=="method" and isinstance(kw.value,ast.Constant) and isinstance(kw.value.value,str):
    print("GLPI_REQUEST_METHOD="+kw.value.value.upper())
print("GLPI_METHOD_REVIEW=MANUAL_CONFIRM_REQUIRED")
print("===== PROMETHEUS ROUTE STATIC REVIEW =====")
fn=ast.parse(inspect.getsource(m.observe))
print("PROMETHEUS_ROUTE_PRESENT="+str(bool(fn.body)))
print("PROMETHEUS_OPERATIONS=REVIEW_REQUIRED")
print("SQL_GUARD_TESTS_FAILED="+str(failures))
print("FS1035_GUARD_QUALIFICATION="+("PASS" if failures==0 else "FAIL"))
raise SystemExit(1 if failures else 0)
'
