#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
bash tests/qualification.sh
bash tests/runtime-contract.sh
bash tests/synthetic-e2e.sh
