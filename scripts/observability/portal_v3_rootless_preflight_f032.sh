#!/usr/bin/env bash
# F-032: read-only, fail-closed rootless inventory. Run as aiops (UID 1001).
set -Eeuo pipefail
umask 077
export DOCKER_HOST=unix:///run/user/1001/docker.sock
export XDG_RUNTIME_DIR=/run/user/1001
unset DOCKER_CONTEXT
ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
status=UNKNOWN
sha="${AIOPS_EXPECTED_SHA:-UNKNOWN}"
printf 'timestamp_utc=%s\nexpected_git_sha=%s\n' "$ts" "$sha"
if [[ "$(id -u)" != 1001 ]]; then echo 'status=UNKNOWN reason=wrong_uid'; exit 2; fi
if [[ ! -S /run/user/1001/docker.sock ]]; then echo 'status=UNKNOWN reason=socket_unavailable'; exit 2; fi
if ! command -v docker >/dev/null; then echo 'status=UNKNOWN reason=docker_cli_unavailable'; exit 2; fi
if ! timeout 12 docker --host "$DOCKER_HOST" info --format '{{.DockerRootDir}}' 2>/dev/null | grep -Fxq '/home/aiops/.local/share/docker'; then
  echo 'status=UNKNOWN reason=unverified_rootless_daemon'; exit 2
fi
# Count complete, untruncated identities; no environment, inspect, volume contents or logs.
if ! containers="$(timeout 20 docker --host "$DOCKER_HOST" ps -aq --no-trunc 2>/dev/null)"; then
  echo 'status=UNKNOWN reason=container_listing_failed'; exit 2
fi
if ! images="$(timeout 20 docker --host "$DOCKER_HOST" image ls -aq --no-trunc 2>/dev/null)"; then
  echo 'status=UNKNOWN reason=image_listing_failed'; exit 2
fi
# Docker image ls may repeat one image ID for multiple tags: deduplicate canonical IDs.
if [[ -n "$containers" ]] && printf '%s\n' "$containers" | grep -Ev '^[0-9a-f]{64}$' >/dev/null; then
  echo 'status=UNKNOWN reason=noncanonical_container_id'; exit 2
fi
if [[ -n "$images" ]] && printf '%s\n' "$images" | grep -Ev '^sha256:[0-9a-f]{64}$' >/dev/null; then
  echo 'status=UNKNOWN reason=noncanonical_image_id'; exit 2
fi
count_unique() { if [[ -z "$1" ]]; then echo 0; else printf '%s\n' "$1" | LC_ALL=C sort -u | wc -l | tr -d ' '; fi; }
printf 'containers_unique=%s\nimages_unique=%s\n' "$(count_unique "$containers")" "$(count_unique "$images")"
printf 'status=INVENTORY_ELIGIBLE_NOT_DEPLOY_APPROVAL\n'
