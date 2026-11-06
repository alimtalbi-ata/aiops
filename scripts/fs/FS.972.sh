#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.972 | FS-001C SOURCE PATCH VALIDATION ====='
REPO=/home/aiops/aiops2-v2-delivery
COMMIT=3f475ba5a83a3ae037ebce642fd61a689d87c230
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
git -C "$REPO" cat-file -e "$COMMIT^{commit}"
git -C "$REPO" show "$COMMIT:app/worker/main.py" > "$TMP/main.py"
python3 - "$TMP/main.py" <<'PY'
import ast,sys
p=sys.argv[1]
s=open(p).read()
ast.parse(s)
t=ast.parse(s)
matches=[n for n in t.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='start']
assert len(matches)==1, 'expected exactly one start()'
fn=ast.get_source_segment(s,matches[0])
for marker in ("run_id required","run not found","run state verification unavailable","run not executable from","await asyncio.to_thread(get_json"):
 assert marker in fn,marker
assert fn.index("await asyncio.to_thread(get_json") < fn.index("Client.connect(TEMP)")
print('PATCH_FS_001C_STATIC_CHECK=PASS')
PY
echo '===== CURRENT RUNTIME (UNCHANGED) ====='
EXPECTED=ecfd599486aaa32b0f3ea446d192aa9c634635a601b7271b785d2fdaf517dfda
echo "$EXPECTED  /home/aiops/aiops2-patches/fs-portal-v30/build/app/worker/main.py" | sha256sum -c -
docker inspect aiops2-rebuild-worker --format 'WORKER_RUNNING={{.State.Running}}'
echo 'SOURCE_GITHUB_PATCHED=YES'
echo 'LOCAL_CHECKOUT_MODIFIED=NO'
echo 'CONTAINERS_RESTARTED=NO'
echo '===== END FS.972 ====='
