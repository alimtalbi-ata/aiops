#!/usr/bin/env bash
# Read-only V1/V30 regression and existing reporter discovery. No credentials or log bodies.
set -Eeuo pipefail
umask 077
export DOCKER_HOST=unix:///run/user/1001/docker.sock
export DOCKER_CONFIG=/home/aiops/.docker
unset DOCKER_CONTEXT
if [[ "$(id -u)" != 1001 || ! -S /run/user/1001/docker.sock ]]; then
  echo 'DEBIAN=UNKNOWN ROOTLESS=UNKNOWN reason=uid_or_socket'; exit 2
fi
command -v docker >/dev/null || { echo 'ROOTLESS=UNKNOWN reason=docker_cli'; exit 2; }
command -v curl >/dev/null || { echo 'HTTP=UNKNOWN reason=curl_cli'; exit 2; }
date -u '+timestamp_utc=%Y-%m-%dT%H:%M:%SZ'
echo 'scope=READ_ONLY V1=7777 V30=7788 LIVE=BLOCKED DEMO_REPLAY=NOT_EXECUTED'
# No daemon fallback, and never query rootful socket.
docker --host "$DOCKER_HOST" info --format 'rootless_security={{json .SecurityOptions}}' 2>/dev/null |
  grep -q 'rootless' || { echo 'ROOTLESS=UNKNOWN reason=daemon_not_attested'; exit 2; }
echo 'ROOTLESS=ATTESTED'
gate_fail=0
bootstrap_review=0
for port in 7777 7788; do
  for route in / /api/portal/bootstrap /api/portal/session /api/portal/scenarios /api/portal/runs /api/fs-demo/health; do
    code=$(curl --noproxy '*' --silent --output /dev/null --max-time 5 --connect-timeout 2 --write-out '%{http_code}' "http://127.0.0.1:${port}${route}" || true)
    [[ "$code" =~ ^[0-9]{3}$ ]] || code=UNKNOWN
    printf 'HTTP port=%s route=%s code=%s\n' "$port" "$route" "$code"
    if [[ "$route" == /api/portal/session && "$code" != 401 ]]; then echo "GATE=FAIL session_$port"; gate_fail=1; fi
    if [[ "$route" == /api/portal/bootstrap ]]; then
      echo "GATE=REVIEW bootstrap_${port}_http_${code}"
      bootstrap_review=1
    fi
  done
done
# Inventory only named Portal candidates and Grafana/GLPI metadata; no env, mount source paths or volume contents.
docker --host "$DOCKER_HOST" ps -a --no-trunc --format '{{.Names}}' |
  grep -E '^(aiops2-rebuild-portal|aiops2-portal-v3-qual-exposed|aiops2-rebuild-grafana|aiops2-rebuild-glpi)$' |
  while IFS= read -r name; do
    docker --host "$DOCKER_HOST" inspect --format 'CONTAINER={{.Name}} STATE={{.State.Status}} IMAGE_ID={{.Image}} RESTART={{.HostConfig.RestartPolicy.Name}} MOUNT_TYPES={{range .Mounts}}{{.Type}},{{end}} MOUNT_COUNT={{len .Mounts}}' "$name" 2>/dev/null ||
      printf 'CONTAINER=%s STATE=UNKNOWN\n' "$name"
  done
# Existing scheduler discovery only. Do not install cron, start a timer, or print commands that might contain secrets.
cron=$(crontab -l 2>/dev/null || true)
for job in aiops-debian-reporter aiops-publish-report; do
  if printf '%s\n' "$cron" | grep -Fq "$job"; then
    printf 'CRON job=%s presence=FOUND_USER_CRONTAB\n' "$job"
  else
    printf 'CRON job=%s presence=UNKNOWN_USER_CRONTAB\n' "$job"
  fi
done
for job in aiops-debian-reporter aiops-publish-report; do
  if systemctl --user list-unit-files --no-legend --no-pager 2>/dev/null | grep -Fq "$job"; then
    printf 'SYSTEMD_USER job=%s presence=FOUND\n' "$job"
  else
    printf 'SYSTEMD_USER job=%s presence=UNKNOWN\n' "$job"
  fi
done
# Receipt discovery is filename-only, bounded to known report location; no content or secrets.
if [[ -d /home/aiops/aiops-debian-audit ]]; then
  find /home/aiops/aiops-debian-audit -maxdepth 5 -type f \( -iname '*receipt*' -o -iname '*publish*' \) -printf '.' 2>/dev/null |
    awk '{ print "REPORT_RECEIPT_CANDIDATE_COUNT=" length($0) }'
else
  echo 'REPORT_RECEIPTS=UNKNOWN location_not_attested'
fi
echo 'ROLLBACK=NO_MUTATION_PERFORMED DB_RESTORE=NOT_EXECUTED'
if (( gate_fail )); then echo 'QUALIFICATION=FAIL reason=session_regression'; exit 1; fi
if (( bootstrap_review )); then echo 'QUALIFICATION=UNKNOWN reason=bootstrap_requires_authenticated_review'; exit 2; fi
echo 'QUALIFICATION=UNKNOWN reason=host_parity_and_rollback_not_attested'; exit 2
