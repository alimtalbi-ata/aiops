#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
command -v zip >/dev/null || { echo 'FAIL|zip_missing'; exit 1; }
command -v sha256sum >/dev/null || { echo 'FAIL|sha256sum_missing'; exit 1; }
command -v python3 >/dev/null || { echo 'FAIL|python3_missing'; exit 1; }
bash tests/static-audit.sh
bash tests/sql-audit.sh
bash -n deploy/*.sh tests/*.sh
python3 -m compileall -q app tests
find app tests -type d -name __pycache__ -prune -exec rm -rf {} +
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
COMMIT="$(git rev-parse --short=12 HEAD 2>/dev/null || printf 'source-tree')"
VERSION="$(awk -F= '/^AIOPS_KIT_VERSION=/{print $2; exit}' config/version.env 2>/dev/null || true)"
VERSION="${VERSION:-2.0.0}"
NAME="AIOps-2.0-Debian-Deployment-Kit-${VERSION}-${STAMP}"
STAGE="$(mktemp -d "${TMPDIR:-/tmp}/aiops-kit.XXXXXX")"
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/$NAME"
tar -C "$ROOT" --exclude='./.git' --exclude='./.env' --exclude='./.env.*' --exclude='./.venv' --exclude='./venv' --exclude='./node_modules' --exclude='./__pycache__' --exclude='*/__pycache__' --exclude='*.pyc' --exclude='./dist' --exclude='./build' --exclude='./*.zip' --exclude='./*.sha256' --exclude='./logs' --exclude='./tmp' --exclude='./.pytest_cache' -cf - . | tar -C "$STAGE/$NAME" -xf -
cat > "$STAGE/$NAME/KIT-MANIFEST.txt" <<EOF
AIOps Debian Deployment Kit
Version: $VERSION
Build UTC: $STAMP
Source commit: $COMMIT
Author: Abdelhalim Talbi

This archive contains source, deployment scripts, configuration templates,
qualification scripts and documentation. It does not contain .env files,
database volumes, production data, or built images.
Qualification claims are limited to results recorded in docs and CI.
EOF
(
  cd "$STAGE/$NAME"
  find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
)
mkdir -p "$ROOT/dist"
OUT="$ROOT/dist/$NAME.zip"
(cd "$STAGE" && zip -qr "$OUT" "$NAME")
(cd "$ROOT/dist" && sha256sum "$NAME.zip" > "$NAME.zip.sha256")
echo "PACKAGE=$OUT"
echo "CHECKSUM=$OUT.sha256"
echo "SOURCE_COMMIT=$COMMIT"
