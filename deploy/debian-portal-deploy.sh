#!/usr/bin/env bash
# DEV-only targeted portal deployment from PR #234; invoked by the Debian cron poller.
set -Eeuo pipefail
umask 077
DEV=/home/aiops/aiops2-auto-deploy/glpi-ai-ticket-enrichment-e2e
ENV=/home/aiops/aiops-v28-demo/.env
STATE=/home/aiops/.local/state/aiops-debian-agent
mkdir -p "$STATE"
LOG="$STATE/portal-deploy.log"
exec > >(tee -a "$LOG") 2>&1
echo "PORTAL_DEPLOY_START $(date -u +%FT%TZ)"
test -f "$DEV/compose.yml" && test -f "$ENV"
test "$(docker inspect aiops2-rebuild-portal --format '{{index .Config.Labels "com.docker.compose.project"}}')" = aiops2-rebuild
curl -fsS --max-time 8 http://127.0.0.1:7777/health >/dev/null
OLD="$(docker inspect aiops2-rebuild-portal --format '{{.Image}}')"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
git init --bare "$TMP/repo.git" >/dev/null
git --git-dir="$TMP/repo.git" fetch --depth=1 https://github.com/alimtalbi-ata/aiops.git refs/pull/234/head
SHA="$(git --git-dir="$TMP/repo.git" rev-parse FETCH_HEAD)"
echo "PORTAL_SOURCE_SHA=$SHA OLD_IMAGE=$OLD"
git --git-dir="$TMP/repo.git" archive FETCH_HEAD app | tar -x -C "$TMP"
TAG="aiops2-portal:pr234-${SHA:0:12}"
docker build -f "$TMP/app/portal/Dockerfile" -t "$TAG" "$TMP/app"
echo "PORTAL_NEW_IMAGE=$(docker image inspect "$TAG" --format '{{.Id}}')"
printf 'services:\n  aiops2-portal:\n    image: %s\n' "$TAG" > "$TMP/new.yml"
printf 'services:\n  aiops2-portal:\n    image: %s\n' "$OLD" > "$TMP/rollback.yml"
cd "$DEV"
base=(docker compose --project-name aiops2-rebuild --env-file "$ENV" -f "$DEV/compose.yml")
"${base[@]}" -f "$TMP/new.yml" config --quiet
rollback() {
  echo "PORTAL_DEPLOY_ROLLBACK $(date -u +%FT%TZ)"
  "${base[@]}" -f "$TMP/rollback.yml" up -d --no-deps --no-build --force-recreate aiops2-portal || true
}
trap rollback ERR
"${base[@]}" -f "$TMP/new.yml" up -d --no-deps --no-build --force-recreate aiops2-portal
ok=0
for i in $(seq 1 40); do
  if [ "$(docker inspect aiops2-rebuild-portal --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}' 2>/dev/null || true)" = healthy ] && curl -fsS --max-time 5 http://127.0.0.1:7777/health >/dev/null 2>&1; then ok=1; break; fi
  sleep 3
done
test "$ok" = 1
trap - ERR
echo "PORTAL_DEPLOY_PASS sha=$SHA image=$(docker inspect aiops2-rebuild-portal --format '{{.Image}}') $(date -u +%FT%TZ)"
