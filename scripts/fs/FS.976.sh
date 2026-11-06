#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.976 | DEPLOY FS-001D TO CANDIDATE SOURCE ====='
REPO=/home/aiops/aiops2-v2-delivery
ROOT=/home/aiops/aiops2-fs-demo-source
REL=integration/worker-fs-candidate/main.py
TARGET="$ROOT/$REL"
EXPECTED=e9be751d2c8596fef78c5cea52d74c5b9182b54f0011cd72c68f61b436387dbd
PATCH_COMMIT=7aa95cfe20ad850b746e100ed23c17103485f07d
PATCH_PATH=patches/fs/PATCH-FS-001D-worker-candidate-source.diff
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
echo "$EXPECTED  $TARGET" | sha256sum -c -
git -C "$REPO" cat-file -e "$PATCH_COMMIT^{commit}"
git -C "$REPO" show "$PATCH_COMMIT:$PATCH_PATH" > "$TMP/patch.diff"
mkdir -p "$TMP/integration/worker-fs-candidate"
cp -p "$TARGET" "$TMP/$REL"
(cd "$TMP" && patch --batch --fuzz=0 --dry-run -p1 < "$TMP/patch.diff")
(cd "$TMP" && patch --batch --fuzz=0 -p1 < "$TMP/patch.diff")
python3 -m py_compile "$TMP/$REL"
python3 - "$TMP/$REL" <<'PY'
import ast,sys
s=open(sys.argv[1]).read();t=ast.parse(s)
f=[n for n in t.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='start']
assert len(f)==1
src=ast.get_source_segment(s,f[0])
for marker in ('run_id required','run not found','run state verification unavailable','run not executable from'):
 assert marker in src,marker
assert src.index('await asyncio.to_thread(get_json')<src.index('Client.connect(TEMP)')
print('PATCH_STATIC_CHECK=PASS')
PY
BACKUP="$TARGET.fs001d.$(date -u +%Y%m%dT%H%M%SZ).bak"
cp -p "$TARGET" "$BACKUP"
if ! cmp -s "$TARGET" "$BACKUP"; then echo 'BACKUP_FAILED'; exit 1; fi
if ! echo "$EXPECTED  $TARGET" | sha256sum -c -; then echo 'SOURCE_CHANGED_ABORT'; exit 1; fi
if ! cp -p "$TMP/$REL" "$TARGET"; then
 cp -p "$BACKUP" "$TARGET"
 echo 'DEPLOY_FAILED_ROLLED_BACK'
 exit 1
fi
if ! cmp -s "$TMP/$REL" "$TARGET"; then
 cp -p "$BACKUP" "$TARGET"
 echo 'VERIFY_FAILED_ROLLED_BACK'
 exit 1
fi
echo 'DEPLOY_STATUS=APPLIED'
echo "BACKUP=$BACKUP"
sha256sum "$TARGET"
echo 'IMAGE_REBUILT=NO'
echo 'CONTAINERS_RESTARTED=NO'
echo '===== END FS.976 ====='
