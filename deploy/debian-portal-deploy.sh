#!/usr/bin/env bash
# Targeted, SHA-pinned DEV portal upgrade; no database/volume mutation.
set -Eeuo pipefail
umask 077
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEV=/home/aiops/aiops2-auto-deploy/glpi-ai-ticket-enrichment-e2e
ENV=/home/aiops/aiops-v28-demo/.env
STATE=/home/aiops/.local/state/aiops-debian-agent
MANIFEST="$ROOT/deploy/debian-portal-release.json"
mkdir -p "$STATE"
exec 9>"$STATE/portal-upgrade.lock"
flock -n 9 || { echo 'PORTAL_DEPLOY=BUSY'; exit 75; }
python3 - "$MANIFEST" > "$STATE/portal-release-sha.tmp" <<'PY'
import json,re,sys
m=json.load(open(sys.argv[1]))
s=m.get('candidate_sha','')
assert m.get('enabled') is True and re.fullmatch('[0-9a-f]{40}',s), 'release not enabled/pinned'
print(s)
PY
PIN="$(cat "$STATE/portal-release-sha.tmp")"
rm -f "$STATE/portal-release-sha.tmp"
test -f "$DEV/compose.yml" && test -f "$ENV"
test "$(docker inspect aiops2-rebuild-portal --format '{{index .Config.Labels "com.docker.compose.project"}}')" = aiops2-rebuild
OLD="$(docker inspect aiops2-rebuild-portal --format '{{.Image}}')"
test -n "$OLD"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
git init --bare "$TMP/source.git" >/dev/null
GIT_TERMINAL_PROMPT=0 git --git-dir="$TMP/source.git" fetch --depth=1 https://github.com/alimtalbi-ata/aiops.git refs/pull/234/head >/dev/null 2>&1
FOUND="$(git --git-dir="$TMP/source.git" rev-parse FETCH_HEAD)"
test "$FOUND" = "$PIN" || { echo "PORTAL_DEPLOY=NO_GO_SOURCE_SHA_CHANGED"; exit 78; }
git --git-dir="$TMP/source.git" archive "$PIN" app | tar -xf - -C "$TMP"
TAG="aiops2-portal:pinned-${PIN:0:12}"
docker build --quiet -f "$TMP/app/portal/Dockerfile" -t "$TAG" "$TMP/app" >/dev/null
NEW="$(docker image inspect "$TAG" --format '{{.Id}}')"
test "$NEW" != "$OLD" || { echo "PORTAL_DEPLOY=NO_GO_IMAGE_UNCHANGED"; exit 78; }
printf 'services:\n  aiops2-portal:\n    image: %s\n    environment:\n      AIOPS_PORTAL_HOST_PORT: "7777"\n' "$TAG" > "$TMP/upgrade.yml"
printf 'services:\n  aiops2-portal:\n    image: %s\n' "$OLD" > "$TMP/rollback.yml"
cd "$DEV"
base=(docker compose --project-name aiops2-rebuild --env-file "$ENV" -f "$DEV/compose.yml")
"${base[@]}" -f "$TMP/upgrade.yml" config --quiet >/dev/null 2>&1
rollback() {
  echo 'PORTAL_DEPLOY=ROLLBACK_ATTEMPTED'
  "${base[@]}" -f "$TMP/rollback.yml" up -d --no-deps --no-build --force-recreate aiops2-portal >/dev/null 2>&1 || echo 'PORTAL_DEPLOY=ROLLBACK_FAILED'
}
trap rollback ERR
"${base[@]}" -f "$TMP/upgrade.yml" up -d --no-deps --no-build --force-recreate aiops2-portal >/dev/null
ok=0
for i in $(seq 1 40); do
  if [ "$(docker inspect aiops2-rebuild-portal --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}' 2>/dev/null || true)" = healthy ] && python3 - <<'PY'
import json,urllib.request
with urllib.request.urlopen('http://127.0.0.1:7777/health',timeout=5) as r:
    v=json.load(r)
    assert r.status==200 and v.get('status')=='ok' and type(v.get('external_port')) is int and v['external_port']==7777
PY
  then ok=1; break; fi
  sleep 3
done
test "$ok" = 1
test "$(docker inspect aiops2-rebuild-portal --format '{{.Image}}')" = "$NEW"
trap - ERR
echo "PORTAL_DEPLOY=PASS candidate_sha=$PIN old_image=$OLD new_image=$NEW"
