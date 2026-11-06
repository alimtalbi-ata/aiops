#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.1002 | PROMETHEUS MEDIA TYPE SOURCE CONTRACT ====='
REPO=/home/aiops/aiops2-v2-delivery
BRANCH=fix/fs-1002-prometheus-metrics-content-type
TMP="$(mktemp -d /tmp/fs1002.XXXXXXXX)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/app/core" "$TMP/app/twin" "$TMP/tests"
for file in app/core/main.py app/twin/main.py tests/test_prometheus_metrics_media_type_fs1002.py; do
 git -C "$REPO" show "origin/$BRANCH:$file" > "$TMP/$file"
done
python3 -m py_compile "$TMP/app/core/main.py" "$TMP/app/twin/main.py" "$TMP/tests/test_prometheus_metrics_media_type_fs1002.py"
python3 - "$TMP" <<'PY'
import ast,pathlib,sys
root=pathlib.Path(sys.argv[1])
for svc in ('core','twin'):
 tree=ast.parse((root/'app'/svc/'main.py').read_text())
 found=False
 for fn in tree.body:
  if not isinstance(fn,(ast.FunctionDef,ast.AsyncFunctionDef)) or fn.name!='metrics':continue
  for d in fn.decorator_list:
   if isinstance(d,ast.Call) and any(isinstance(a,ast.Constant) and a.value=='/metrics' for a in d.args):
    assert any(k.arg=='response_class' and isinstance(k.value,ast.Name) and k.value.id=='PlainTextResponse' for k in d.keywords)
    found=True
 assert found,svc+' metrics contract missing'
 print('METRICS_MEDIA_TYPE_CONTRACT='+svc+':PASS')
print('SOURCE_COMPILE=PASS')
PY
echo 'NOTE=Twin HTTP 503 requires separate diagnosis; this test does not claim to fix it'
echo 'HTTP_WRITES=0'
echo 'PRODUCTION_RESTARTED=NO'
echo '===== END FS.1002 ====='
