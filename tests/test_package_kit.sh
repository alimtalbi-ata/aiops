#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
LOG="$TMP/package.log"
( cd "$ROOT"; bash deploy/package.sh ) | tee "$LOG"
PACKAGE="$(sed -n 's/^PACKAGE=//p' "$LOG" | tail -n 1)"
CHECKSUM="$(sed -n 's/^CHECKSUM=//p' "$LOG" | tail -n 1)"
[[ -n "$PACKAGE" && -f "$PACKAGE" ]] || { echo 'FAIL|package_missing'; exit 1; }
[[ -n "$CHECKSUM" && -f "$CHECKSUM" ]] || { echo 'FAIL|checksum_missing'; exit 1; }
(cd "$(dirname "$CHECKSUM")" && sha256sum -c "$(basename "$CHECKSUM")")
unzip -t "$PACKAGE" >/dev/null
LIST="$TMP/list.txt"
unzip -Z1 "$PACKAGE" > "$LIST"
grep -q '/KIT-MANIFEST.txt$' "$LIST"
grep -q '/SHA256SUMS$' "$LIST"
grep -q '/deploy/install.sh$' "$LIST"
grep -q '/docs/DEBIAN-DEPLOYMENT-KIT.md$' "$LIST"
grep -q '/config/.env.example$' "$LIST"
if grep -Eq '(^|/)[.]env$' "$LIST"; then
  echo 'FAIL|environment_secret_file_in_package'
  exit 1
fi
( cd "$TMP"; unzip -q "$PACKAGE"; cd "$(find . -name KIT-MANIFEST.txt -printf '%h\n' | head -n 1)"; sha256sum -c SHA256SUMS )
if [[ "${KEEP_PACKAGE:-0}" != "1" ]]; then rm -f "$PACKAGE" "$CHECKSUM"; fi
echo 'PACKAGE_KIT_TEST=PASS'
