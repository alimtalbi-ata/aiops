#!/usr/bin/env bash
# SHA-pinned portal-only DEV rollout. No DB, GLPI, volume or other service writes.
set -Eeuo pipefail
umask 077
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEV=/home/aiops/aiops2-auto-deploy/glpi-ai-ticket-enrichment-e2e
ENV=/home/aiops/aiops-v28-demo/.env
STATE=/home/aiops/.local/state/aiops-debian-agent
mkdir -p "$STATE"
exec 9>"$STATE/portal-upgrade.lock"
flock -n 9 || { echo 'PORTAL_DEPLOY=BUSY'; exit 75; }
PIN="$(python3 - "$ROOT/deploy/debian-portal-release.json" <<'PY'
import json,re,sys
m=json.load(open(sys.argv[1])); s=m.get('candidate_sha','')
if m.get('enabled') is not True or not isinstance(s,str) or not re.fullmatch(r'[0-9a-f]{40}',s):
    raise SystemExit('PORTAL_DEPLOY=NO_GO_RELEASE_NOT_PINNED')
print(s)
PY
)"
test -f "$DEV/compose.yml" && test -f "$ENV" || { echo 'PORTAL_DEPLOY=NO_GO_MISSING_COMPOSE_OR_ENV'; exit 78; }
test "$(docker inspect aiops2-rebuild-portal --format '{{index .Config.Labels "com.docker.compose.project"}}')" = aiops2-rebuild
test "$(docker inspect aiops2-rebuild-portal --format '{{index .Config.Labels "com.docker.compose.service"}}')" = aiops2-portal
# This legacy deploy path is only qualified for a zero-mount, healthchecked
# Portal. The current Debian Portal has persistent mounts and no Docker
# healthcheck: fail explicitly before building or recreating anything.
HEALTH_STATUS="$(docker inspect aiops2-rebuild-portal --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}')"
if [ "$HEALTH_STATUS" != healthy ]; then
  echo 'PORTAL_DEPLOY=NO_GO_DOCKER_HEALTHCHECK_UNAVAILABLE_OR_UNHEALTHY'
  echo 'PORTAL_DEPLOY=NEXT_ACTION_READONLY_PREFLIGHT_AND_HTTP_READINESS'
  exit 78
fi
MOUNT_COUNT="$(docker inspect aiops2-rebuild-portal --format '{{len .Mounts}}')"
if [ "$MOUNT_COUNT" != 0 ]; then
  echo 'PORTAL_DEPLOY=NO_GO_PERSISTENT_MOUNTS_REQUIRE_BACKUP_AND_RESTORE'
  exit 78
fi
docker inspect aiops2-rebuild-portal --format '{{json .NetworkSettings.Ports}}' |
python3 -c 'import json,sys; p=json.load(sys.stdin).get("777/tcp") or []; assert len(p)==1 and p[0].get("HostPort")=="7777"'
OLD="$(docker inspect aiops2-rebuild-portal --format '{{.Image}}')"
OLD_CONTAINER="$(docker inspect aiops2-rebuild-portal --format '{{.Id}}')"
docker image inspect "$OLD" >/dev/null
TMP="$(mktemp -d)"
mutated=0
success=0
NEW=""
compose() { docker compose --project-name aiops2-rebuild --env-file "$ENV" -f "$DEV/compose.yml" "$@"; }
rollback() {
  if [ "$mutated" = 1 ] && [ "$success" != 1 ]; then
    echo 'PORTAL_DEPLOY=ROLLBACK_ATTEMPTED'
    compose -f "$TMP/rollback.yml" up -d --no-deps --no-build --force-recreate aiops2-portal >/dev/null 2>&1 ||
      echo 'PORTAL_DEPLOY=ROLLBACK_FAILED'
  fi
}
finish() {
  code=$?
  trap - EXIT
  rollback
  python3 - "$STATE/portal-deploy-result.json" "$PIN" "$OLD" "$NEW" "$OLD_CONTAINER" "$success" "$mutated" "$code" <<'PY'
import datetime,json,os,sys,tempfile
path,pin,old,new,container,success,mutated,code=sys.argv[1:]
payload={'schema':'aiops.debian-portal-deploy-result.v1',
 'collected_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'candidate_sha':pin,'previous_image_id':old,'new_image_id':new or None,
 'previous_container_id':container,'deployment_executed':mutated=='1',
 'docker_mutations':int(mutated),'status':'PASS' if success=='1' and code=='0' else 'FAIL',
 'exit_code':int(code),'rollback_attempted':mutated=='1' and success!='1',
 'human_glpi_e2e':'NOT_VERIFIED','scope':'aiops2-rebuild-portal:7777'}
fd,tmp=tempfile.mkstemp(prefix='.portal-deploy-',dir=os.path.dirname(path))
try:
 with os.fdopen(fd,'w') as f: json.dump(payload,f,sort_keys=True); f.write('\n')
 os.replace(tmp,path)
finally:
 if os.path.exists(tmp): os.unlink(tmp)
PY
  rm -rf "$TMP"
  exit "$code"
}
trap finish EXIT

# Stable instrumentation-only merges must not rebuild an unchanged pinned
# portal source. Require both the running container tag and immutable image ID
# to match the already-present pin; otherwise follow the normal rebuild path.
SHORT="$(printf '%s' "$PIN" | cut -c1-12)"
TAG="aiops2-portal:pinned-$SHORT"
RUNNING_TAG="$(docker inspect aiops2-rebuild-portal --format '{{.Config.Image}}')"
TAG_IMAGE="$(docker image inspect "$TAG" --format '{{.Id}}' 2>/dev/null || true)"
if [ "$RUNNING_TAG" = "$TAG" ] && [ "$TAG_IMAGE" = "$OLD" ]; then
  python3 - <<'PY'
import json,urllib.request
with urllib.request.urlopen('http://127.0.0.1:7777/health',timeout=5) as r:
    v=json.load(r)
    assert r.status==200 and v.get('status')=='ok'
    assert type(v.get('external_port')) is int and v['external_port']==7777
PY
  /usr/bin/python3 "$ROOT/deploy/debian-portal-ux-contracts.py" || exit 78
  success=1
  echo 'PORTAL_DEPLOY=NOOP_PINNED_RUNNING_IMAGE'
  exit 0
fi

# PR ref is only transport; exact immutable commit equality is mandatory.
git init --bare "$TMP/source.git" >/dev/null
GIT_TERMINAL_PROMPT=0 git --git-dir="$TMP/source.git" fetch --depth=1 \
  https://github.com/alimtalbi-ata/aiops.git refs/pull/234/head >/dev/null 2>&1
test "$(git --git-dir="$TMP/source.git" rev-parse FETCH_HEAD)" = "$PIN" ||
  { echo 'PORTAL_DEPLOY=NO_GO_SOURCE_SHA_CHANGED'; exit 78; }
git --git-dir="$TMP/source.git" archive "$PIN" app | tar -xf - -C "$TMP"
SHORT="$(printf '%s' "$PIN" | cut -c1-12)"
TAG="aiops2-portal:pinned-$SHORT"
docker build --quiet -f "$TMP/app/portal/Dockerfile" -t "$TAG" "$TMP/app" >/dev/null
NEW="$(docker image inspect "$TAG" --format '{{.Id}}')"
test -n "$NEW"
if [ "$NEW" = "$OLD" ]; then
  # Idempotent re-entry: no recreate, and never claim a fresh Docker mutation.
  python3 - <<'PY'
import json,urllib.request
with urllib.request.urlopen('http://127.0.0.1:7777/health',timeout=5) as r:
    v=json.load(r)
    assert r.status==200 and v.get('status')=='ok'
    assert type(v.get('external_port')) is int and v['external_port']==7777
PY
  /usr/bin/python3 "$ROOT/deploy/debian-portal-ux-contracts.py" || exit 78
  success=1
  echo 'PORTAL_DEPLOY=NOOP_ALREADY_SAME_IMAGE'
  exit 0
fi

# Redacted rollback record: no copies of .env, no secrets in published receipts.
python3 - "$STATE/portal-rollback-manifest.json" "$OLD" "$OLD_CONTAINER" "$PIN" "$DEV/compose.yml" "$ENV" <<'PY'
import datetime,hashlib,json,os,sys,tempfile
path,old,container,pin,compose,env=sys.argv[1:]
digest=lambda p:hashlib.sha256(open(p,'rb').read()).hexdigest()
payload={'schema':'aiops.debian-portal-rollback.v1',
 'collected_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'previous_image_id':old,'previous_container_id':container,'candidate_sha':pin,
 'compose_sha256':digest(compose),'env_sha256':digest(env),
 'restore':'compose up --no-deps --no-build portal with previous image ID',
 'volumes_modified':False}
fd,tmp=tempfile.mkstemp(prefix='.portal-rollback-',dir=os.path.dirname(path))
with os.fdopen(fd,'w') as f: json.dump(payload,f,sort_keys=True); f.write('\n')
os.replace(tmp,path)
PY
printf 'services:\n  aiops2-portal:\n    image: "%s"\n    environment:\n      AIOPS_PORTAL_HOST_PORT: "7777"\n' "$TAG" > "$TMP/upgrade.yml"
printf 'services:\n  aiops2-portal:\n    image: "%s"\n' "$OLD" > "$TMP/rollback.yml"
# Resolved config is parsed in-memory; never log secrets or interpolated config.
compose -f "$TMP/upgrade.yml" config --format json 2>/dev/null |
python3 -c 'import json,sys; s=json.load(sys.stdin)["services"]["aiops2-portal"]; assert s.get("container_name")=="aiops2-rebuild-portal"; assert str(s.get("environment",{}).get("AIOPS_PORTAL_HOST_PORT"))=="7777"; assert any(str(p.get("published"))=="7777" and str(p.get("target"))=="777" and p.get("protocol","tcp")=="tcp" for p in s.get("ports",[])); assert not s.get("volumes")'
compose -f "$TMP/rollback.yml" config --quiet >/dev/null 2>&1
mutated=1
compose -f "$TMP/upgrade.yml" up -d --no-deps --no-build --force-recreate aiops2-portal >/dev/null
ok=0
for i in $(seq 1 40); do
  if [ "$(docker inspect aiops2-rebuild-portal --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}' 2>/dev/null || true)" = healthy ] &&
    python3 - <<'PY'
import json,urllib.request
with urllib.request.urlopen('http://127.0.0.1:7777/health',timeout=5) as r:
    v=json.load(r)
    assert r.status==200 and v.get('status')=='ok'
    assert type(v.get('external_port')) is int and v['external_port']==7777
PY
  then ok=1; break; fi
  sleep 3
done
test "$ok" = 1
test "$(docker inspect aiops2-rebuild-portal --format '{{.Image}}')" = "$NEW"
/usr/bin/python3 "$ROOT/deploy/debian-portal-ux-contracts.py" || exit 78
success=1
echo "PORTAL_DEPLOY=PASS candidate_sha=$PIN old_image=$OLD new_image=$NEW"
