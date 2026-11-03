#!/usr/bin/env bash
# Existing poller only; opt-in SHA-pinned five-service ACME sandbox upgrade.
# Never touch portal :7777, GLPI, Temporal DB, persistent volumes or other stacks.
set -Eeuo pipefail
umask 077
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEV=/home/aiops/aiops2-auto-deploy/glpi-ai-ticket-enrichment-e2e
ENV=/home/aiops/aiops-v28-demo/.env
STATE=/home/aiops/.local/state/aiops-debian-agent
MANIFEST="$ROOT/deploy/debian-acme-sandbox-release.json"
mkdir -p "$STATE"
exec 9>"$STATE/acme-sandbox-upgrade.lock"
flock -n 9 || { echo 'ACME_UPGRADE=BUSY'; exit 75; }
PIN="$(python3 - "$MANIFEST" <<'PY'
import json,re,sys
m=json.load(open(sys.argv[1]))
s=m.get('candidate_sha','')
if m.get('enabled') is not True or not isinstance(s,str) or not re.fullmatch('[0-9a-f]{40}',s):
    raise SystemExit('ACME_UPGRADE=NO_GO_MANIFEST_DISABLED_OR_UNPINNED')
print(s)
PY
)"
# Idempotency and fail-stop: a previous exact-PIN PASS is never rebuilt again.
# Verify current container/image/health and canonical portal before accepting it.
# A previous same-PIN FAIL or drift requires a new reviewed release SHA.
prior="$(python3 - "$STATE/acme-sandbox-upgrade.json" "$PIN" <<'PY'
import json,os,subprocess,sys,urllib.request
path,pin=sys.argv[1:]
if not os.path.isfile(path):
 print('NO_PRIOR_RECEIPT');raise SystemExit(0)
try:
 if os.path.getsize(path)>16384:raise ValueError('oversized')
 r=json.load(open(path))
 if r.get('source_sha')!=pin:
  print('NO_PRIOR_RECEIPT');raise SystemExit(0)
 if r.get('status')!='PASS' or r.get('exit_code')!=0:
  print('NO_GO_PRIOR_SAME_PIN_FAILURE');raise SystemExit(0)
 rows=r.get('images')
 if (r.get('docker_container_mutations')!=1 or r.get('docker_image_builds')!=5
     or r.get('pg16_scratch_restore')!='PASS' or r.get('portal_7777_untouched') is not True
     or not isinstance(rows,list) or len(rows)!=5
     or {x.get('service') for x in rows}!=set(('core','twin','policy','worker','simulator'))):
  raise ValueError('invalid_receipt')
 for row in rows:
  p=subprocess.run(['docker','inspect','aiops2-rebuild-'+row['service'],
                    '--format','{{.Image}} {{.Id}} {{if .State.Health}}{{.State.Health.Status}}{{end}}'],
                   capture_output=True,text=True,timeout=8,check=False)
  parts=p.stdout.strip().split()
  if (p.returncode!=0 or len(parts)!=3 or parts[2]!='healthy'
      or parts[0]!=row.get('observed_image_id')
      or parts[1]!=row.get('observed_container_id')
      or row.get('image_changed') is not True):
   raise ValueError('container_drift')
 with urllib.request.urlopen('http://127.0.0.1:7777/health',timeout=5) as response:
  h=json.load(response)
  if (response.status!=200 or h.get('status')!='ok'
      or type(h.get('external_port')) is not int or h['external_port']!=7777):
   raise ValueError('portal_drift')
 print('ALREADY_APPLIED')
except (OSError,ValueError,TypeError,KeyError,subprocess.TimeoutExpired,
        urllib.error.URLError,AssertionError):
 print('NO_GO_PRIOR_RECEIPT_OR_RUNTIME_DRIFT')
PY
)"
case "$prior" in
  NO_PRIOR_RECEIPT) ;;
  ALREADY_APPLIED) echo 'ACME_UPGRADE=ALREADY_APPLIED_VERIFIED'; exit 0 ;;
  *) echo "ACME_UPGRADE=$prior"; exit 78 ;;
esac
SOURCE_PR="$(python3 - "$MANIFEST" <<'PY'
import json,sys
m=json.load(open(sys.argv[1]))
p=m.get('source_pr',358)
if type(p) is not int or not 1<=p<=99999:
 raise SystemExit('ACME_UPGRADE=NO_GO_SOURCE_PR_INVALID')
print(p)
PY
)"
test -f "$DEV/compose.yml" && test -f "$ENV" || { echo 'ACME_UPGRADE=NO_GO_COMPOSE_OR_ENV_MISSING'; exit 78; }
TMP="$(mktemp -d "$STATE/.acme-upgrade-XXXXXX")"
mutated=0
success=0
rollback_status=NOT_REQUIRED
backup_sha=NOT_CREATED
image_builds=0
restore_status=NOT_RUN
restore_created=0
restore_db="aiops_acme_restore_$(printf '%s' "$PIN" | cut -c1-12)"
receipt="$STATE/acme-sandbox-upgrade.json"
services="core twin policy worker simulator"
compose() { docker compose --project-name aiops2-rebuild --env-file "$ENV" -f "$DEV/compose.yml" "$@"; }
rollback() {
  if [ "$mutated" = 1 ] && [ "$success" != 1 ]; then
    rollback_status=ATTEMPTED
    if compose -f "$TMP/rollback.yml" up -d --no-deps --no-build --force-recreate aiops2-core aiops2-twin aiops2-policy aiops2-worker aiops2-simulator >/dev/null 2>&1; then
      rollback_status=RECREATED_UNVERIFIED
      for svc in $services; do
        if [ "$(docker inspect "aiops2-rebuild-$svc" --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}' 2>/dev/null)" != healthy ]; then
          rollback_status=FAILED_HEALTH
        fi
      done
      if [ "$rollback_status" = RECREATED_UNVERIFIED ]; then rollback_status=HEALTHY; fi
    else
      rollback_status=FAILED_RECREATE
    fi
  fi
}
finish() {
  code=$?
  trap - EXIT
  rollback
  if [ "$restore_created" = 1 ]; then
    if docker exec aiops2-rebuild-postgres dropdb -U aiops "$restore_db" >/dev/null 2>&1; then
      restore_created=0
    else
      restore_status=FAILED_SCRATCH_CLEANUP
    fi
  fi
  python3 - "$receipt" "$PIN" "$success" "$mutated" "$image_builds" "$code" "$rollback_status" "$backup_sha" "$TMP/images.tsv" "$TMP/health.tsv" "$TMP/portal-health.tsv" "$ROOT" "$DEV" "$restore_status" <<'PY'
import datetime,json,os,sys,tempfile,subprocess
path,pin,success,mutated,builds,code,rollback,backup,images,health,portal,stable,dev,restore_status=sys.argv[1:]
def sha(path):
 try:
  p=subprocess.run(['git','-C',path,'rev-parse','HEAD'],capture_output=True,text=True,timeout=5,check=False)
  return p.stdout.strip() if p.returncode==0 and len(p.stdout.strip())==40 else None
 except (OSError,subprocess.TimeoutExpired):return None
probes={}
try:
 for line in open(health):
  name,http,status=line.strip().split('\t')
  probes[name]={'http_status':int(http),'json_status':status}
except (OSError,ValueError):pass
portal_probe=None
try:
 parts=open(portal).read().strip().split('\t')
 if len(parts)==3:portal_probe={'http_status':int(parts[0]),'json_status':parts[1],'external_port':int(parts[2])}
except (OSError,ValueError):pass
rows=[]
try:
 for line in open(images):
  parts=line.strip().split('\t')
  if len(parts)==4:
   item=dict(service=parts[0],previous_image_id=parts[1],
             rollback_tag=parts[2],candidate_tag=parts[3])
   try:
    inspect=subprocess.run(['docker','inspect','aiops2-rebuild-'+parts[0],
       '--format','{{.Image}} {{.Id}} {{if .State.Health}}{{.State.Health.Status}}{{end}}'],
       capture_output=True,text=True,timeout=5,check=False)
    fields=inspect.stdout.strip().split()
    if inspect.returncode==0 and len(fields)==3:
     item.update(observed_image_id=fields[0],observed_container_id=fields[1],
                 observed_health=fields[2],image_changed=fields[0]!=parts[1])
   except (OSError,subprocess.TimeoutExpired):pass
   item.update(probes.get(parts[0],{}))
   rows.append(item)
except OSError: pass
payload={'schema':'aiops.debian-acme-sandbox-upgrade.v1',
 'collected_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'source_sha':pin,'stable_checkout_sha':sha(stable),'dev_checkout_sha':sha(dev),
 'portal_http':portal_probe,'scope':'aiops2-rebuild core/twin/policy/worker/simulator only',
 'portal_7777_untouched':True,'glpi_write':False,'live_effects_allowed':False,
 'docker_container_mutations':int(mutated),'docker_image_builds':int(builds),
 'status':'PASS' if success=='1' and code=='0' else 'FAIL',
 'exit_code':int(code),'rollback_status':rollback,'pg16_backup_sha256':backup,
 'migrations':'011-019 additive; retain on app rollback',
 'pg16_scratch_restore':restore_status,'images':rows,
 'e2e':'SEPARATE_RECEIPT_REQUIRED'}
fd,tmp=tempfile.mkstemp(prefix='.acme-upgrade-receipt-',dir=os.path.dirname(path))
try:
 with os.fdopen(fd,'w') as f:
  os.fchmod(f.fileno(),0o600)
  json.dump(payload,f,sort_keys=True);f.write('\n')
 os.replace(tmp,path)
finally:
 if os.path.exists(tmp):os.unlink(tmp)
PY
  rm -rf "$TMP"
  exit "$code"
}
trap finish EXIT

# Ref is transport only: never deploy mutable PR HEAD unless it matches PIN.
git init --bare "$TMP/source.git" >/dev/null
GIT_TERMINAL_PROMPT=0 git --git-dir="$TMP/source.git" fetch --depth=1 \
  https://github.com/alimtalbi-ata/aiops.git "refs/pull/$SOURCE_PR/head" >/dev/null 2>&1
test "$(git --git-dir="$TMP/source.git" rev-parse FETCH_HEAD)" = "$PIN" ||
  { echo 'ACME_UPGRADE=NO_GO_SOURCE_PIN_MISMATCH'; exit 78; }
git --git-dir="$TMP/source.git" archive "$PIN" app db/migrations | tar -xf - -C "$TMP"
test -f "$TMP/db/migrations/017_acme_sandbox_prepared_transition.sql"
test -f "$TMP/db/migrations/018_acme_sandbox_terminal_ticket_receipt.sql"
test -f "$TMP/db/migrations/019_acme_sandbox_twin_topology.sql"

# Read-only inspect canonical Compose ownership, mounts and health BEFORE build.
compose config --quiet >/dev/null 2>&1
for svc in $services; do
  name="aiops2-rebuild-$svc"
  test "$(docker inspect "$name" --format '{{index .Config.Labels "com.docker.compose.project"}}')" = aiops2-rebuild
  test "$(docker inspect "$name" --format '{{index .Config.Labels "com.docker.compose.service"}}')" = "aiops2-$svc"
  test "$(docker inspect "$name" --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}')" = healthy
  test "$(docker inspect "$name" --format '{{len .Mounts}}')" = 0
  old="$(docker inspect "$name" --format '{{.Image}}')"
  docker image inspect "$old" >/dev/null
  rollback_tag="aiops2-acme-rollback-$svc:$(printf '%s' "$PIN" | cut -c1-12)"
  candidate_tag="aiops2-acme-sandbox-$svc:$(printf '%s' "$PIN" | cut -c1-12)"
  docker tag "$old" "$rollback_tag"
  printf '%s\t%s\t%s\t%s\n' "$svc" "$old" "$rollback_tag" "$candidate_tag" >> "$TMP/images.tsv"
done
# Dedicated sandbox signing secret stays local, 0600, never printed or published.
python3 - "$STATE/acme-twin-hmac.key" <<'PY'
import os,secrets,sys,tempfile
p=sys.argv[1]
if not os.path.exists(p):
 fd,tmp=tempfile.mkstemp(prefix='.acme-twin-key-',dir=os.path.dirname(p))
 try:
  with os.fdopen(fd,'w') as f:
   os.fchmod(f.fileno(),0o600);f.write(secrets.token_hex(32)+'\n')
  os.replace(tmp,p)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
st=os.stat(p)
if st.st_mode & 0o077 or not os.path.isfile(p):raise SystemExit(78)
key=open(p).read().strip()
if len(key)<64 or not all(x in '0123456789abcdef' for x in key):raise SystemExit(78)
PY
AIOPS_ACME_TWIN_APPROVAL_KEY="$(cat "$STATE/acme-twin-hmac.key")"
export AIOPS_ACME_TWIN_APPROVAL_KEY

# Override only five existing Compose services. No second stack, no portal.
python3 - "$TMP/images.tsv" "$TMP/upgrade.yml" "$TMP/rollback.yml" <<'PY'
import sys
rows=[line.strip().split('\t') for line in open(sys.argv[1])]
for path,rollback in ((sys.argv[2],False),(sys.argv[3],True)):
 with open(path,'w') as f:
  f.write('services:\n')
  for svc,old,oldtag,newtag in rows:
   f.write('  aiops2-'+svc+':\n    image: '+(oldtag if rollback else newtag)+'\n')
   f.write('    environment:\n      AIOPS_ACME_SANDBOX_ENABLED: "'+('false' if rollback else 'true')+'"\n')
   if not rollback:
    if svc=='core':f.write('      TWIN_URL: http://aiops2-twin:811\n')
    if svc=='twin':
     f.write('      CORE_URL: http://aiops2-core:810\n')
     f.write('      AIOPS_INTERNAL_TOKEN: $'+'{AIOPS_INTERNAL_TOKEN:?}\n')
     f.write('      AIOPS_ACME_TWIN_APPROVAL_KEY: $'+'{AIOPS_ACME_TWIN_APPROVAL_KEY:?}\n')
    if svc=='policy':
     f.write('      CORE_URL: http://aiops2-core:810\n      TWIN_URL: http://aiops2-twin:811\n')
    if svc=='simulator':
     f.write('      CORE_URL: http://aiops2-core:810\n      TWIN_URL: http://aiops2-twin:811\n      POLICY_URL: http://aiops2-policy:813\n      WORKER_URL: http://aiops2-worker:815\n')
     f.write('    networks:\n      - aiops2-control\n      - aiops2-execution\n')
PY
# The private Compose env file is used; never log interpolated configuration.
compose -f "$TMP/upgrade.yml" config --quiet >/dev/null 2>&1

# Build immutable images before touching DB/containers.
for svc in $services; do
  tag="$(awk -F '\t' -v s="$svc" '$1==s{print $4}' "$TMP/images.tsv")"
  # Every image carries immutable source provenance, including unchanged
  # components in the five-service guarded upgrade. This ensures all five
  # images actually change on a new reviewed PIN (no meaningless tag-only GO).
  docker build --quiet --label "aiops.source_sha=$PIN" \\
    -f "$TMP/app/$svc/Dockerfile" -t "$tag" "$TMP/app" >/dev/null
  test "$(docker image inspect "$tag" --format '{{index .Config.Labels "aiops.source_sha"}}')" = "$PIN"
  image_builds=$((image_builds+1))
done

# Native PG16 backup + listing before any additive migration; no restore to live DB.
BACKUP="$STATE/acme-sandbox-preupgrade-$(printf '%s' "$PIN" | cut -c1-12).pgcustom"
docker exec aiops2-rebuild-postgres pg_dump -U aiops -d aiops -Fc > "$BACKUP"
chmod 600 "$BACKUP"
test -s "$BACKUP"
docker exec -i aiops2-rebuild-postgres pg_restore --list < "$BACKUP" >/dev/null
backup_sha="$(sha256sum "$BACKUP" | awk '{print $1}')"
# RG-ACME-20: prove a native restore into a NEW disposable database on the
# existing PG16 server before migrations or any service recreation. Never
# restore over live aiops or drop a database that was not created by this job.
test "$(docker exec aiops2-rebuild-postgres psql -U aiops -d postgres -Atqc \
 "select count(*) from pg_database where datname='$restore_db'")" = 0 || \
 { echo 'ACME_UPGRADE=NO_GO_SCRATCH_DB_ALREADY_EXISTS'; exit 78; }
db_bytes="$(docker exec aiops2-rebuild-postgres psql -U aiops -d postgres -Atqc \
 "select pg_database_size('aiops')")"
free_kb="$(docker exec aiops2-rebuild-postgres df -Pk /var/lib/postgresql/data | awk 'NR==2{print $4}')"
test "$free_kb" -gt 0 && test $((free_kb*1024)) -gt $((db_bytes*2+1073741824)) || \
 { echo 'ACME_UPGRADE=NO_GO_RESTORE_DISK_HEADROOM'; exit 78; }
docker exec aiops2-rebuild-postgres createdb -U aiops -T template0 "$restore_db"
restore_created=1
docker exec -i aiops2-rebuild-postgres pg_restore -U aiops -d "$restore_db" \
  --no-owner --no-acl --exit-on-error < "$BACKUP" >/dev/null
test "$(docker exec aiops2-rebuild-postgres psql -U aiops -d "$restore_db" -Atqc \
 "select to_regclass('aiops.runs') is not null and to_regclass('aiops.incidents') is not null")" = t
docker exec aiops2-rebuild-postgres dropdb -U aiops "$restore_db"
restore_created=0
restore_status=PASS
# Installed 009/010 prerequisites must be real, never silently inferred.
test "$(docker exec aiops2-rebuild-postgres psql -U aiops -d aiops -Atqc \
 "select to_regclass('aiops.analysis_records') is not null and to_regclass('aiops.evidence') is not null")" = t
for n in 011 012 013 014 015 016 017 018 019; do
  file="$(find "$TMP/db/migrations" -maxdepth 1 -type f -name "$n"_\*.sql -print -quit)"
  test -n "$file"
  cat "$file" >> "$TMP/migrate.sql"
  printf '\n' >> "$TMP/migrate.sql"
done
docker exec -i aiops2-rebuild-postgres psql -U aiops -d aiops -v ON_ERROR_STOP=1 -1 -f - < "$TMP/migrate.sql" >/dev/null

# Exactly five existing services, no dependencies and no portal recreate.
mutated=1
compose -f "$TMP/upgrade.yml" up -d --no-deps --no-build --force-recreate \
  aiops2-core aiops2-twin aiops2-policy aiops2-worker aiops2-simulator >/dev/null
for i in $(seq 1 30); do
  all_healthy=1
  for svc in $services; do
    test "$(docker inspect "aiops2-rebuild-$svc" --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}')" = healthy || all_healthy=0
  done
  if [ "$all_healthy" = 1 ]; then break; fi
  sleep 2
done
test "$all_healthy" = 1
# Strict container-local HTTP JSON health and unchanged canonical host portal :7777.
for svc in $services; do
  case "$svc" in
    core) port=810;; twin) port=811;; policy) port=813;;
    worker) port=815;; simulator) port=816;;
  esac
  docker exec -i "aiops2-rebuild-$svc" python3 - "$port" <<'PY'
import json,sys,urllib.request
with urllib.request.urlopen('http://127.0.0.1:'+sys.argv[1]+'/health',timeout=5) as response:
 value=json.load(response)
 assert response.status==200 and value.get('status')=='ok'
PY
  printf '%s\t200\tok\n' "$svc" >> "$TMP/health.tsv"
done
python3 - "$TMP/portal-health.tsv" <<'PY'
import json,sys,urllib.request
with urllib.request.urlopen('http://127.0.0.1:7777/health',timeout=5) as response:
 value=json.load(response)
 assert response.status==200 and value.get('status')=='ok'
 assert type(value.get('external_port')) is int and value['external_port']==7777
open(sys.argv[1],'w').write('200\tok\t7777\n')
PY
# A successful deployment must attest a changed image and actual container recreation.
for svc in $services; do
  old="$(awk -F '\t' -v s="$svc" '$1==s{print $2}' "$TMP/images.tsv")"
  new="$(docker inspect "aiops2-rebuild-$svc" --format '{{.Image}}')"
  test "$old" != "$new"
  test "$(docker inspect "aiops2-rebuild-$svc" --format '{{index .Config.Labels "aiops.source_sha"}}')" = "$PIN"
done
success=1
echo 'ACME_UPGRADE=PASS_IMAGES_RECREATED_E2E_SEPARATE'
