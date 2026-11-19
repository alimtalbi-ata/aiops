#!/usr/bin/env bash
# Run from assembled checkout; never on runtime image.
set -euo pipefail
umask 077
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
: "${QA_PYTHON:?Set QA_PYTHON to isolated virtualenv interpreter}"
"$QA_PYTHON" -c 'import sys; assert sys.prefix != sys.base_prefix, "isolated venv required"'
for name in PORTAL_VIEWER_TOKEN PORTAL_OPERATOR_TOKEN QA_VIEWER_TOKEN; do unset "$name"; done
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT
cd frontend/mission-control
TSC=./node_modules/.bin/tsc
"$TSC" --version
node --version
"$TSC" --strict --target ES2020 --module commonjs --outDir "$OUT/a" src/ux/operational.test.ts src/ux/analytics.test.ts
node "$OUT/a/operational.test.js"
node "$OUT/a/analytics.test.js"
"$TSC" --strict --skipLibCheck --target ES2022 --module commonjs --lib ES2022,DOM --outDir "$OUT/c" src/actions/providers.test.ts
node -e 'require(process.argv[1]).verifyProviderContracts().then(()=>console.log("provider contracts PASS"),e=>{console.error(e);process.exitCode=1})' "$OUT/c/providers.test.js"
cd "$ROOT"
PYTHONPATH=app "$QA_PYTHON" -m pytest -q tests/mission_data tests/mission_actions
