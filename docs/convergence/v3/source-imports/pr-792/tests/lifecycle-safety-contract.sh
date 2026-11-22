#!/usr/bin/env bash
# Negative lifecycle test: an installation flag may not retire old containers.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/deploy"
cp "$ROOT/deploy/install.sh" "$ROOT/deploy/big-bang.sh" "$TMP/deploy/"
for entry in install.sh big-bang.sh; do
  if ( cd "$TMP" && RETIRE_LEGACY=1 CONFIRM_BIG_BANG=YES bash "deploy/$entry" ) > "$TMP/result.txt" 2>&1; then
    echo "FAIL|retirement_allowed_during_install|$entry"
    exit 1
  fi
  grep -Fq 'FAIL|' "$TMP/result.txt" || {
    echo "FAIL|retirement_rejection_unreported|$entry"
    exit 1
  }
  [[ ! -f "$TMP/.env" ]] || {
    echo "FAIL|retirement_rejection_wrote_environment|$entry"
    exit 1
  }
done
grep -Fq 'CONFIRM_DATA_LOSS' "$ROOT/deploy/restore.sh"
grep -Fq 'CONFIRM_STACK_ID' "$ROOT/deploy/restore.sh"
grep -Fq 'RESTORE_VERIFY_ONLY=PASS' "$ROOT/deploy/restore.sh"
echo "LIFECYCLE_SAFETY=PASS|installer_retirement=blocked|bigbang_retirement=blocked|restore=explicit"
