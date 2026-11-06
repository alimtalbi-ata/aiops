#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.973 | FS-001C SOURCE SYNC PREFLIGHT ====='
REPO=/home/aiops/aiops2-v2-delivery
COMMIT=3f475ba5a83a3ae037ebce642fd61a689d87c230
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
git -C "$REPO" cat-file -e "$COMMIT^{commit}"
git -C "$REPO" show "$COMMIT:app/worker/main.py" > "$TMP/patched.py"
python3 - "$TMP/patched.py" <<'PY'
import ast,sys
p=sys.argv[1];s=open(p).read();ast.parse(s)
t=ast.parse(s);f=[n for n in t.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='start']
assert len(f)==1
src=ast.get_source_segment(s,f[0])
for term in ('run_id required','run not found','run state verification unavailable','run not executable from'):
 assert term in src,term
assert src.index('await asyncio.to_thread(get_json')<src.index('Client.connect(TEMP)')
print('PATCHED_SOURCE_STATIC=PASS')
PY
echo '===== 1. SOURCE COMPARISON ====='
for base in /home/aiops/aiops2-v2-delivery /home/aiops/aiops2-fs-demo-source; do
 f="$base/app/worker/main.py"
 if [[ ! -f "$f" ]]; then echo "SOURCE_MISSING=$f"; continue; fi
 echo "SOURCE=$f"
 sha256sum "$f"
 if cmp -s "$f" "$TMP/patched.py"; then echo 'PATCHED_SOURCE_MATCH=YES'; else echo 'PATCHED_SOURCE_MATCH=NO'; fi
 python3 - "$f" "$TMP/patched.py" <<'PY'
import ast,sys
def normalized(p):
 s=open(p).read();t=ast.parse(s)
 fn=[n for n in t.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='start']
 assert len(fn)==1
 return ast.dump(t,include_attributes=False),ast.get_source_segment(s,fn[0])
a,fa=normalized(sys.argv[1]);b,fb=normalized(sys.argv[2])
print('AST_EQUAL='+str(a==b))
print('START_EQUAL='+str(fa==fb))
PY
done
echo '===== 2. BUILD CONFIG ====='
for f in /home/aiops/aiops2-fs-demo-source/integration/worker-fs-candidate/Dockerfile /home/aiops/aiops2-fs-demo-source/integration/worker-fs-candidate/compose.fs-worker.yml /home/aiops/aiops2-fs-demo-source/app/worker/Dockerfile; do
 echo "CONFIG=$f"
 if [[ -f "$f" ]]; then sed -n '1,100p' "$f"; else echo 'MISSING'; fi
done
echo '===== 3. REPO STATUS ====='
git -C "$REPO" status --short -- app/worker/main.py
echo 'FILES_MODIFIED=NO'
echo 'CONTAINERS_RESTARTED=NO'
echo '===== END FS.973 ====='
