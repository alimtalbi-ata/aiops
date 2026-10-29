#!/usr/bin/env bash
# One-command, non-destructive deployment from an extracted cumulative release.
# This wrapper intentionally contains NO credentials and NEVER retires legacy.
set -Eeuo pipefail
umask 077
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ "${RETIRE_LEGACY:-0}" != "0" ]]; then
  echo "FAIL|legacy_retirement_prohibited_in_one_command_install"
  exit 3
fi
exec bash "$ROOT/deploy/install-isolated.sh" "$@"
