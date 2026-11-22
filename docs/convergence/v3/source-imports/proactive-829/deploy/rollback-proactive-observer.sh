#!/usr/bin/env bash
# Remove only the AIOps2 proactive observer cron entries. Preserve all other jobs.
set -Eeuo pipefail
umask 077
[[ "$(id -un)" == aiops ]]
[[ "$(hostname -s | tr '[:upper:]' '[:lower:]')" == srv-deb-05 ]]
state="$HOME/.local/state/aiops2-proactive"
mkdir -p "$state"
exec 9>"$state/install.lock"
flock -n 9
backup="$(mktemp "$state/crontab-before-rollback.XXXXXXXX")"
current="$(mktemp "$state/crontab-current.XXXXXXXX")"
next="$(mktemp "$state/crontab-rollback.XXXXXXXX")"
verify="$(mktemp "$state/crontab-verify.XXXXXXXX")"
trap 'rm -f "$current" "$next" "$verify"' EXIT
crontab -l > "$backup"
cp "$backup" "$current"
awk '!/# AIOPS2_PROACTIVE_OBSERVER_V1$/ { print }' "$current" > "$next"
if cmp -s "$current" "$next"; then
  echo "No AIOps2 proactive observer cron entries found; crontab unchanged. Backup=$backup"
  exit 0
fi
crontab "$next"
if ! crontab -l > "$verify" || ! cmp -s "$next" "$verify"; then
  crontab "$backup"
  echo "Rollback verification failed; original crontab restored from $backup" >&2
  exit 1
fi
echo "AIOps2 proactive observer cron entries removed; all unrelated entries preserved. Backup=$backup"
