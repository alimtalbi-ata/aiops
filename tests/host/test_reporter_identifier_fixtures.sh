#!/usr/bin/env bash
# Offline regression fixtures for exact reporter identifiers. No host access.
set -euo pipefail
cron_match() {
  local job="$1"
  awk -v job="$job" '
    /^[[:space:]]*(#|$)/ {next}
    $0 ~ "(^|[[:space:]/;])" job "(\\.sh)?([[:space:];]|$)" {found=1; exit}
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
expect_yes unit_match aiops-publish-report <<< 'aiops-publish-report.timer enabled'
expect_yes unit_match aiops-debian-reporter <<< 'aiops-debian-reporter.service enabled'
expect_no unit_match aiops-publish-report <<< 'backup-aiops-publish-report-old.service enabled'
expect_no unit_match aiops-publish-report <<< 'aiops-publish-report-disabled.timer enabled'
expect_no unit_match aiops-publish-report <<< 'aiops-publish-report.service.bak enabled'
echo 'PASS reporter identifier fixtures (11 assertions); host/runtime NOT_INSPECTED'
