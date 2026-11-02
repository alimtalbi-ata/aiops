#!/usr/bin/env bash
# Disabled: legacy unpinned PR-head fetch and forced Compose recreate are not safe.
# A later exact-SHA, reviewed, rollback-qualified upgrade must replace this stub.
set -Eeuo pipefail
printf '%s\n' 'PORTAL_DEPLOY_NO_GO: backup, immutable image, Compose and rollback gates pending' >&2
exit 78
