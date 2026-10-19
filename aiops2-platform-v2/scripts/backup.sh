#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
ROOT=/home/aiops/aiops2
[[ -d "$ROOT" && -f "$ROOT/.env" ]] || { echo AIOPS2_INSTALL_NOT_FOUND;exit 2; }
mkdir -p "$ROOT/backups"
OUT="$ROOT/backups/aiops2-config-$(date +%Y%m%d-%H%M%S).tar.gz"
tar --exclude='./data' --exclude='./backups' --exclude='./reports' -czf "$OUT" -C "$ROOT" .
chmod 600 "$OUT";sha256sum "$OUT" > "$OUT.sha256"
echo "BACKUP=$OUT";cat "$OUT.sha256";echo "Archive contains .env; keep private."