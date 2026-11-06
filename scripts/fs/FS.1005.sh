#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.1005 | TWIN FILESYSTEM METRICS FUNCTION FORENSICS ====='
echo 'MODE=READ_ONLY'
echo '===== RUNTIME CALLABLE SOURCE AND EXCEPTION ====='
docker exec -i aiops2-rebuild-twin python - <<'PY'
import inspect,traceback,os,sys
os.chdir('/app/twin')
sys.path[:0]=['/app/twin','/app']
import main as m
fn=getattr(m,'fs_lab_metrics',None)
print('CALLABLE_PRESENT='+str(fn is not None))
if fn is not None:
 print('CALLABLE_MODULE='+str(getattr(fn,'__module__',None)))
 print('CALLABLE_SIGNATURE='+str(inspect.signature(fn)))
 try:
  print('CALLABLE_SOURCE_BEGIN')
  print(inspect.getsource(fn)[:6500])
  print('CALLABLE_SOURCE_END')
 except Exception as e: print('SOURCE_ERROR='+type(e).__name__+' '+str(e)[:180])
 try:
  result=fn()
  print('CALL_RESULT_TYPE='+type(result).__name__)
  print('CALL_RESULT_STATUS='+str(getattr(result,'status_code',None)))
  print('CALL_RESULT_MEDIA_TYPE='+str(getattr(result,'media_type',None)))
  print('CALL_RESULT_BODY='+repr(getattr(result,'body',b'')[:1200]))
 except Exception as e:
  print('CALL_EXCEPTION='+type(e).__name__)
  print('CALL_EXCEPTION_DETAIL='+str(getattr(e,'detail',str(e)))[:500])
  traceback.print_exc(limit=5)
PY
echo '===== RUNTIME MODULE PATHS ====='
docker exec -i aiops2-rebuild-twin python - <<'PY'
import os,sys,inspect
os.chdir('/app/twin')
sys.path[:0]=['/app/twin','/app']
import main as m
print('MAIN_FILE='+str(inspect.getsourcefile(m)))
fn=getattr(m,'fs_lab_metrics',None)
if fn:
 mod=__import__(fn.__module__,fromlist=['*'])
 print('METRICS_MODULE_FILE='+str(inspect.getsourcefile(mod)))
PY
echo '===== OBSERVATION SCHEMA ONLY ====='
docker exec -i aiops2-rebuild-postgres psql -U aiops -d aiops -Atc "select column_name||'|'||data_type from information_schema.columns where table_schema='aiops' and table_name='observations' order by ordinal_position" 2>/dev/null || echo 'SCHEMA_QUERY_UNAVAILABLE'
echo '===== SAFETY ====='
echo 'HTTP_WRITES=0'
echo 'PRODUCTION_RESTARTED=NO'
echo '===== END FS.1005 ====='
