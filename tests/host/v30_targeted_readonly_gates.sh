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
http_unknown=0
bootstrap_review=0
route_review=0
mount_review=0
receipt_review=0
for port in 7777 7788; do
  for route in / /api/portal/bootstrap /api/portal/session /api/portal/scenarios /api/portal/runs /api/fs-demo/health; do
    code=$(curl --noproxy '*' --silent --output /dev/null --max-time 5 --connect-timeout 2 --write-out '%{http_code}' "http://127.0.0.1:${port}${route}" || true)
    [[ "$code" =~ ^[1-5][0-9]{2}$ ]] || code=UNKNOWN
    if [[ "$code" == UNKNOWN ]]; then http_unknown=1; fi
    printf 'HTTP port=%s route=%s code=%s\n' "$port" "$route" "$code"
    if [[ "$route" == /api/portal/session && "$code" != 401 && "$code" != UNKNOWN ]]; then echo "GATE=FAIL session_$port"; gate_fail=1; fi
    case "$port:$route" in
      7777:/api/portal/scenarios|7777:/api/fs-demo/health|7777:/api/portal/runs|7788:/api/portal/runs) expected=404 ;;
      7788:/api/portal/scenarios|7788:/api/fs-demo/health) expected=200 ;;
      *) expected='' ;;
    esac
    if [[ -n "$expected" && "$code" != "$expected" ]]; then
      echo "GATE=REVIEW route_contract port=$port expected=$expected observed=$code"
      route_review=1
    fi
    if [[ "$route" == /api/portal/bootstrap ]]; then
      echo "GATE=REVIEW bootstrap_${port}_http_${code}"
      bootstrap_review=1
    fi
  done
done
# Inventory only named Portal candidates and Grafana/GLPI metadata; no env, mount source paths or volume contents.
for name in aiops2-portal-v3-qual-exposed aiops2-rebuild-grafana aiops2-rebuild-glpi aiops2-rebuild-glpi-db; do
  if ! docker --host "$DOCKER_HOST" container inspect "$name" >/dev/null 2>&1; then
    echo "MOUNTS container=$name state=UNKNOWN"; mount_review=1; continue
  fi
  mounts=$(docker --host "$DOCKER_HOST" inspect --format '{{range .Mounts}}{{.Destination}}|{{.Type}}|{{if eq .Type "volume"}}{{.Name}}{{else}}BIND{{end}}{{println}}{{end}}' "$name" 2>/dev/null) || {
    echo "MOUNTS container=$name state=UNKNOWN"; mount_review=1; continue;
  }
  case "$name" in
    aiops2-rebuild-grafana)
      if ! grep -Fq '|volume|aiops2-rebuild-grafana-data' <<<"$mounts" ||
         ! grep -Fq '/etc/grafana/provisioning|bind|BIND' <<<"$mounts"; then
        echo "MOUNTS container=$name state=REVIEW"; mount_review=1
      fi ;;
    aiops2-rebuild-glpi)
      if ! grep -Fq '|volume|aiops2-rebuild-glpi-data' <<<"$mounts"; then echo "MOUNTS container=$name state=REVIEW"; mount_review=1; fi ;;
    aiops2-rebuild-glpi-db)
      if ! grep -Fq '|volume|aiops2-rebuild-glpi-db-data' <<<"$mounts"; then echo "MOUNTS container=$name state=REVIEW"; mount_review=1; fi ;;
    aiops2-portal-v3-qual-exposed)
      if grep -Eq '^/app/portal[|/]' <<<"$mounts"; then echo 'MOUNTS container=V30 state=REVIEW'; mount_review=1; fi ;;
  esac
  echo "MOUNTS container=$name metadata_only=YES"
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
# Receipt candidates: counts only, never names, contents, commands or credentials.
report_dir=/home/aiops/aiops-debian-audit/reports/SRV-DEB-05/2026-11-12
if [[ -d "$report_dir" ]]; then
  receipt_count=$(find "$report_dir" -maxdepth 4 -type f \\( -iname '*receipt*' -o -iname '*publish*' \\) -printf '.' 2>/dev/null | wc -c)
  echo "REPORT_RECEIPT_CANDIDATE_COUNT=$receipt_count"
  if (( receipt_count == 0 )); then receipt_review=1; fi
  echo 'REPORT_RECEIPT_CORRELATION=UNKNOWN requires_job_timestamp_and_published_sha'
else
  echo 'REPORT_RECEIPTS=UNKNOWN location_not_attested'; receipt_review=1
fi
echo 'ROLLBACK=NO_MUTATION_PERFORMED DB_RESTORE=NOT_EXECUTED'
if (( gate_fail )); then echo 'QUALIFICATION=FAIL reason=session_regression'; exit 1; fi
if (( http_unknown )); then echo 'QUALIFICATION=UNKNOWN reason=http_transport_unavailable'; exit 2; fi
if (( route_review || mount_review || receipt_review )); echo 'QUALIFICATION=UNKNOWN reason=route_mount_or_receipt_review'; exit 2; fi
if (( bootstrap_review )); then echo 'QUALIFICATION=UNKNOWN reason=bootstrap_requires_authenticated_review'; exit 2; fi
echo 'QUALIFICATION=UNKNOWN reason=host_parity_and_rollback_not_attested'; exit 2
