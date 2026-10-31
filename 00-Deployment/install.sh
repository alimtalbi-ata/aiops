#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
SRC="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${AIOPS2_ROOT:-/home/aiops/aiops2-v8}"
if [[ -e "$TARGET" ]]; then echo "FAIL|TARGET_EXISTS|$TARGET"; exit 2; fi
bash "$SRC/deploy/preflight.sh"
mkdir -p "$TARGET"
cp -a "$SRC/." "$TARGET/"
cd "$TARGET"
# Generate unique per-install secrets using the canonical environment initializer.
# Never inject shared/default credentials into a new server.
bash deploy/init-env.sh
bash deploy/check-secrets.sh .env
docker compose --env-file .env config >/dev/null
echo "PASS|INSTALL_TREE|$TARGET"
echo "NEXT|bash 00-Deployment/start.sh"
