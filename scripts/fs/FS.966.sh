#!/usr/bin/env bash
set -Eeuo pipefail
[[ "${DEPLOY_FS_001B:-NO}" == YES ]] || { echo 'Set DEPLOY_FS_001B=YES'; exit 2; }
REPO=/home/aiops/aiops2-v2-delivery
ROOT=/home/aiops/aiops2-patches/fs-portal-v30/build
TARGET="$ROOT/app/worker/main.py"
CONTAINER=aiops2-rebuild-worker
COMMIT=4f0b05c5ad7721d2c5c954ee9704ae07bc8f677e
PATCH=patches/fs/PATCH-FS-001B-worker-core-404.diff
EXPECTED=d624369f6399f9a3a88521a359f9385eb6cf09ce710e2af402466a274fddbc2d
echo '===== FS.966 | DEPLOY FS-001B ====='
echo "$EXPECTED  $TARGET" | sha256sum -c -
TMP=$(mktemp -d)
BACKUP="$HOME/worker-main.fs001b.$(date -u +%Y%m%dT%H%M%SZ).bak"
CHANGED=NO
cleanup(){ rm -rf "$TMP"; }
rollback(){
 rc=$?
 trap - ERR
 if [[ "$CHANGED" == YES ]]; then
  echo 'ROLLBACK=STARTED'
  cp "$BACKUP" "$TARGET"
  docker restart "$CONTAINER" || true
 fi
 cleanup
 exit "$rc"
}
trap rollback ERR
mkdir -p "$TMP/app/worker"
cp -p "$TARGET" "$TMP/app/worker/main.py"
git -C "$REPO" show "$COMMIT:$PATCH" > "$TMP/patch.diff"
git -C "$TMP" apply --check "$TMP/patch.diff"
git -C "$TMP" apply "$TMP/patch.diff"
python3 -m py_compile "$TMP/app/worker/main.py"
docker exec -i "$CONTAINER" python - <<'PY'
import asyncio
from temporalio.client import Client
async def main():
 c=await Client.connect('aiops2-rebuild-temporal:7233',namespace='default')
 count=0
 async for _ in c.list_workflows('ExecutionStatus="Running"'):
  count+=1
 print('ACTIVE_WORKFLOWS='+str(count))
 if count: raise SystemExit('REFUSED: active workflows')
asyncio.run(main())
PY
cp -p "$TARGET" "$BACKUP"
CHANGED=YES
cat "$TMP/app/worker/main.py" > "$TARGET"
docker restart "$CONTAINER"
test "$(docker inspect -f '{{.State.Running}}' "$CONTAINER")" = true
HOST_SHA=$(sha256sum "$TARGET" | awk '{print $1}')
RUNTIME_SHA=$(docker exec "$CONTAINER" sha256sum /app/worker/main.py | awk '{print $1}')
test "$HOST_SHA" = "$RUNTIME_SHA"
test "$HOST_SHA" != "$EXPECTED"
docker exec -i "$CONTAINER" python - <<'PY'
import ast
from pathlib import Path
s=Path('/app/worker/main.py').read_text()
ast.parse(s)
assert "run not found" in s
assert "run state verification unavailable" in s
print('RUNTIME_PATCH_CHECK=PASS')
PY
CHANGED=NO
trap - ERR
cleanup
echo 'DEPLOY_STATUS=APPLIED'
echo "BACKUP=$BACKUP"
echo "NEW_SHA256=$HOST_SHA"
echo '===== END FS.966 ====='
