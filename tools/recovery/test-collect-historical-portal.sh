#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
SCRIPT="$(cd "$(dirname "$0")" && pwd)/collect-historical-portal.sh"
bash -n "$SCRIPT"

TMP="$(mktemp -d)"
trap 'rm -rf -- "$TMP"' EXIT
R33="$TMP/r33"
OUT="$TMP/out"
V1="$TMP/v1.tar"
V145="$TMP/v145.tar"
mkdir -p "$R33/app/static" "$TMP/v1/app/app/static" "$TMP/v145/app/app/static" "$OUT"
printf 'from fastapi import FastAPI\napp = FastAPI()\n' > "$R33/app/main.py"
printf 'fastapi==0.115.0\n' > "$R33/requirements.txt"
printf 'FROM python:3.12-slim\n' > "$R33/Dockerfile"
printf '<html>R33</html>\n' > "$R33/app/static/index.html"
printf 'console.log("R33");\n' > "$R33/app/static/app.js"
printf 'from fastapi import FastAPI\napp = FastAPI()\n# v1\n' > "$TMP/v1/app/app/main.py"
printf '<html>V1</html>\n' > "$TMP/v1/app/app/static/index.html"
printf 'console.log("V1");\n' > "$TMP/v1/app/app/static/app.js"
printf 'from fastapi import FastAPI\napp = FastAPI()\n# v145\n' > "$TMP/v145/app/app/main.py"
printf '<html>V145</html>\n' > "$TMP/v145/app/app/static/index.html"
printf 'console.log("V145");\n' > "$TMP/v145/app/app/static/app.js"
tar -cf "$V1" -C "$TMP/v1" app
tar -cf "$V145" -C "$TMP/v145" app

OUTPUT="$(R33_SOURCE="$R33" V1_EXPORT="$V1" V145_EXPORT="$V145" OUT_ROOT="$OUT" bash "$SCRIPT")"
printf '%s\n' "$OUTPUT"
PACKAGE="$(printf '%s\n' "$OUTPUT" | sed -n 's/^PACKAGE=//p' | head -1)"
[[ -n "$PACKAGE" && -f "$PACKAGE" ]]
sha256sum -c "$PACKAGE.sha256"
tar -tzf "$PACKAGE" | grep -q 'RECOVERY-MANIFEST.txt'
tar -tzf "$PACKAGE" | grep -q 'reports/STATIC-ANALYSIS.txt'
tar -tzf "$PACKAGE" | grep -q 'reports/SOURCE-INVENTORY.tsv'
tar -tzf "$PACKAGE" | grep -q 'diff/V1-vs-V145.diff'
tar -tzf "$PACKAGE" | grep -q 'diff/R33-vs-V145.diff'
printf 'TEST_RESULT=PASS\n'
