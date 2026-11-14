#!/usr/bin/env bash
# Offline regression fixtures for exact reporter identifiers. No host access.
set -euo pipefail
cron_match() {
  local job="$1" mode="${2:-user}"
  awk -v job="$job" -v mode="$mode" '
    /^[[:space:]]*(#|$)/ {next}
    {
      line=$0
      sub(/^[[:space:]]+/, "", line)
      sub(/[[:space:]]+#.*/, "", line)
      n=split(line, a, /[[:space:]]+/)
      offset=(mode=="system" ? 6 : 5)
      if (n <= offset) next
      i=offset+1
      while (i<=n && a[i] ~ /^[A-Za-z_][A-Za-z0-9_]*=/) i++
      if (i>n) next
      executable=a[i]
      sub(/^.*\//, "", executable)
      if (executable==job || executable==job ".sh") {found=1; exit}
    }
    END {exit !found}
  '
}
unit_match() {
  local job="$1"
  awk -v job="$job" '$1 ~ ("^" job "\\.(service|timer|path)$") {found=1} END {exit !found}'
}
expect_yes() { "$@" || { echo "FAIL expected match" >&2; exit 1; }; }
expect_no() { if "$@"; then echo "FAIL unexpected match" >&2; exit 1; fi; }
expect_yes cron_match aiops-publish-report <<< '*/5 * * * * /home/aiops/bin/aiops-publish-report.sh'
expect_yes cron_match aiops-debian-reporter <<< '0 * * * * /home/aiops/bin/aiops-debian-reporter'
expect_no cron_match aiops-publish-report <<< '*/5 * * * * /bin/aiops-publish-report-disabled'
expect_no cron_match aiops-publish-report <<< '# */5 * * * * /bin/aiops-publish-report.sh'
expect_no cron_match aiops-publish-report <<< '*/5 * * * * /bin/backup-aiops-publish-report-old'
expect_no cron_match aiops-publish-report <<< '*/5 * * * * echo aiops-publish-report-disabled'
expect_no cron_match aiops-publish-report <<< '* * * * * /bin/true # aiops-publish-report'
expect_no cron_match aiops-debian-reporter <<< '* * * * * /bin/true # /usr/local/bin/aiops-debian-reporter.sh'
expect_yes unit_match aiops-publish-report <<< 'aiops-publish-report.timer enabled'
expect_yes unit_match aiops-debian-reporter <<< 'aiops-debian-reporter.service enabled'
expect_no unit_match aiops-publish-report <<< 'backup-aiops-publish-report-old.service enabled'
expect_no unit_match aiops-publish-report <<< 'aiops-publish-report-disabled.timer enabled'
expect_no unit_match aiops-publish-report <<< 'aiops-publish-report.service.bak enabled'
expect_no cron_match aiops-publish-report <<< '*/5 * * * * /bin/echo aiops-publish-report'
expect_no cron_match aiops-debian-reporter <<< '*/5 * * * * /usr/bin/printf aiops-debian-reporter'
expect_no cron_match aiops-publish-report system <<< '*/5 * * * * root /bin/echo aiops-publish-report'
expect_yes cron_match aiops-publish-report system <<< '*/5 * * * * aiops /home/aiops/bin/aiops-publish-report.sh'
expect_yes cron_match aiops-debian-reporter system <<< '0 * * * * aiops /home/aiops/bin/aiops-debian-reporter'
expect_no cron_match aiops-publish-report <<< '*/5 * * * * /bin/true ; /home/aiops/bin/aiops-publish-report.sh'
expect_yes cron_match aiops-publish-report <<< '  */5 * * * * /home/aiops/bin/aiops-publish-report.sh'
expect_yes cron_match aiops-debian-reporter <<< 
\t0 * * * * /home/aiops/bin/aiops-debian-reporter'
expect_yes cron_match aiops-publish-report system <<< '  */5 * * * * aiops /home/aiops/bin/aiops-publish-report.sh'
expect_no cron_match aiops-publish-report <<< '  */5 * * * * /bin/echo aiops-publish-report'
echo 'PASS reporter identifier fixtures (23 assertions); host/runtime NOT_INSPECTED'
