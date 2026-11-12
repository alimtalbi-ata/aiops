#!/usr/bin/env bash
set -Eeuo pipefail
echo '===== FS.1021 | PERSIST CORE IMAGE WITHOUT RESTART ====='
MODE="${1:---plan}"
[[ "$MODE" == --plan || "$MODE" == --execute ]] || { echo 'USAGE: FS.1021.sh --plan|--execute'; exit 2; }
CORE=aiops2-rebuild-core
TWIN=aiops2-rebuild-twin
PROM=aiops2-rebuild-prometheus
PROJECT=aiops2-metrics-cutover
OLD=aiops2-core:fs-real-registration-20261105
NEW=aiops2-core:fs1017-metrics-candidate-20261106
F1=/home/aiops/aiops-prometheus-image-patch/compose.metrics-cutover.yml
F2=/home/aiops/aiops2-patches/fs-core-real-registration/compose.fs-core.override.yml
WD=/home/aiops/aiops-prometheus-image-patch
SHA1=97cddc9e452294b0934a995f9c54d3f746e9e17146c03fbbf58f29ba81303f13
SHA2=94cb772053ebd0a9bdf74b6ac488175080aa69595d8128485815b20ef1012734
EXPECTED_ID=sha256:c31c2412af358fe93c680fa8f7193307c5b316aaba57a4b31b42296304818d67
test -f "$F1" && test -f "$F2"
test "$(sha256sum "$F1" | cut -d' ' -f1)" = "$SHA1" || { echo 'NO_GO=BASE_COMPOSE_HASH_CHANGED'; exit 1; }
test "$(sha256sum "$F2" | cut -d' ' -f1)" = "$SHA2" || { echo 'NO_GO=OVERRIDE_COMPOSE_HASH_CHANGED'; exit 1; }
test "$(docker inspect --format '{{.Image}}' "$CORE")" = "$EXPECTED_ID" || { echo 'NO_GO=CORE_IMAGE_CHANGED'; exit 1; }
test "$(docker inspect --format '{{.State.Running}}' "$CORE")" = true
test "$(docker inspect --format '{{.State.Running}}' "$TWIN")" = true
docker image inspect "$NEW" >/dev/null
docker compose version >/dev/null
render() { (cd "$WD" && docker compose -p "$PROJECT" -f "$F1" -f "$F2" config --format json); }
render | python3 -c '
import json,sys
s=json.load(sys.stdin)["services"]["aiops2-core"]
assert s["image"]=="aiops2-core:fs-real-registration-20261105",s["image"]
print("PRECHANGE_COMPOSE_IMAGE=PASS")
'
echo '===== LOCATE UNIQUE EFFECTIVE IMAGE DEFINITION ====='
TARGET="$(python3 - "$F1" "$F2" "$OLD" <<'PY'
import sys,re
files=sys.argv[1:3];old=sys.argv[3]
matches=[]
for f in files:
 text=open(f).read()
 # Strictly accept a single literal image declaration (no templating).
 for line in text.splitlines():
  if re.fullmatch(r'\s*image:\s*'+re.escape(old)+r'\s*(?:#.*)?',line):
   matches.append(f)
assert len(matches)==1, "Expected exactly one matching image declaration; found "+str(len(matches))
print(matches[0])
PY
)"
echo "TARGET_COMPOSE_FILE=$TARGET"
echo '===== PREFLIGHT CORE/TWIN PROMETHEUS ====='
docker exec "$PROM" wget -qO- http://127.0.0.1:9090/api/v1/targets | python3 -c '
import json,sys
a=json.load(sys.stdin)["data"]["activeTargets"]
for j in ("aiops2-core","aiops2-twin"):
 t=[x for x in a if x.get("labels",{}).get("job")==j]
 assert len(t)==1 and t[0]["health"]=="up",(j,t)
print("PROMETHEUS_PREFLIGHT=PASS")
'
if [[ "$MODE" == --plan ]]; then
 echo 'FS1021_RESULT=PLAN_PASS'
 echo 'FILES_MODIFIED=NO'
 echo 'PRODUCTION_RESTARTED=NO'
 exit 0
fi
[[ "${FS1021_APPROVE_PERSISTENCE:-}" == YES ]] || { echo 'NO_GO=EXPLICIT_APPROVAL_REQUIRED'; exit 2; }
BACKUP="${TARGET}.fs1021-backup-20261106"
[[ ! -e "$BACKUP" ]] || { echo 'NO_GO=BACKUP_ALREADY_EXISTS'; exit 1; }
cp -p -- "$TARGET" "$BACKUP"
echo "BACKUP_FILE=$BACKUP"
MODIFIED=0
SUCCESS=0
rollback() {
 local rc=$?
 trap - EXIT ERR INT TERM
 if [[ "$MODIFIED" == 1 && "$SUCCESS" != 1 ]]; then
  echo '===== RESTORE ORIGINAL COMPOSE FILE ====='
  if cp -p -- "$BACKUP" "$TARGET"; then echo 'COMPOSE_ROLLBACK=RESTORED'; else echo 'COMPOSE_ROLLBACK=FAILED'; fi
 fi
 exit "$rc"
}
trap rollback EXIT ERR INT TERM
python3 - "$TARGET" "$OLD" "$NEW" <<'PY'
import os,re,sys,tempfile
p,old,new=sys.argv[1:]
st=os.stat(p)
with open(p,'rb') as f: raw=f.read()
s=raw.decode('utf-8')
pat=r'(?m)^(\s*image:\s*)'+re.escape(old)+r'(\s*(?:#.*)?)$'
updated,n=re.subn(pat,lambda m:m.group(1)+new+m.group(2),s)
assert n==1,n
fd,tmp=tempfile.mkstemp(prefix='.fs1021-',dir=os.path.dirname(p))
try:
 os.fchmod(fd,st.st_mode & 0o7777)
 with os.fdopen(fd,'wb') as f:
  f.write(updated.encode('utf-8'));f.flush();os.fsync(f.fileno())
 os.replace(tmp,p)
except:
 try:os.unlink(tmp)
 except OSError:pass
 raise
print("COMPOSE_IMAGE_REPLACEMENT=PASS")
PY
MODIFIED=1
echo '===== VERIFY PERSISTENCE AND LIVE SERVICES ====='
(cd "$WD" && docker compose -p "$PROJECT" -f "$F1" -f "$F2" config --quiet)
render | python3 -c '
import json,sys
s=json.load(sys.stdin)["services"]["aiops2-core"]
assert s["image"]=="aiops2-core:fs1017-metrics-candidate-20261106",s["image"]
print("PERSISTENT_CORE_IMAGE=ALIGNED")
'
[[ "$(docker inspect --format '{{.Image}}' "$CORE")" == "$EXPECTED_ID" ]]
[[ "$(docker inspect --format '{{.State.Running}}' "$CORE")" == true ]]
[[ "$(docker inspect --format '{{.State.Running}}' "$TWIN")" == true ]]
docker exec -i "$CORE" python -B - <<'PY'
import urllib.request
with urllib.request.urlopen("http://127.0.0.1:810/metrics",timeout=8) as r:
 assert r.status==200
 assert r.headers.get("Content-Type","").startswith("text/plain")
 assert b"aiops_runs_total " in r.read()
print("CORE_LIVE_METRICS=PASS")
PY
docker exec "$PROM" wget -qO- http://127.0.0.1:9090/api/v1/targets | python3 -c '
import json,sys
a=json.load(sys.stdin)["data"]["activeTargets"]
for j in ("aiops2-core","aiops2-twin"):
 t=[x for x in a if x.get("labels",{}).get("job")==j]
 assert len(t)==1 and t[0]["health"]=="up",(j,t)
 print("PROMETHEUS_"+j.upper().replace("-","_")+"=UP")
'
SUCCESS=1
echo 'PRODUCTION_RESTARTED=NO'
echo 'TWIN_UNCHANGED=YES'
echo 'ROLLBACK_BACKUP_RETAINED=YES'
echo 'FS1021_RESULT=PASS'
echo '===== END FS.1021 ====='
