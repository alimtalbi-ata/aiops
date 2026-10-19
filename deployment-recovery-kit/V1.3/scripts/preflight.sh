#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
echo "AIOps2 recovery preflight — READ ONLY"
date --iso-8601=seconds
printf 'HOST=%s\n' "$(hostname)"
printf 'USER=%s\n' "$(id -un)"
printf 'DISK='; df -h /home/aiops | tail -1
for p in /home/aiops/aiops2-v8-r4/00-Deployment /home/aiops/aiops-platform /home/aiops/.temporal-stage-20261017-171712 /home/aiops/exports/AIOPS-R33-LOGICAL-20261007-112249/03-SOURCES/V69/stack; do
  if [[ -e "$p" ]]; then printf 'FOUND '; stat -c '%A %U:%G %n' "$p"; else printf 'MISSING %s\n' "$p"; fi
done
if command -v docker >/dev/null 2>&1; then
  docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' | grep -E '^(NAMES|aiops2_)' || true
else
  echo DOCKER_CLI_NOT_FOUND
fi
echo PREFLIGHT_COMPLETE
