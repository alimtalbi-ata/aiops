#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
echo "FS1134_MODE=ISOLATED_INTELLIGENCE_PROVIDER_TO_KPI_INTEGRATION"
echo "FS1134_PRODUCTION_MUTATION=NONE"
docker run --rm -v "$ROOT:/src:ro" -w /src python:3.12-slim sh -ec '
  python -m pip install -q "fastapi>=0.110" "pydantic>=2" "requests>=2" "httpx2"
  PYTHONPATH=/src/app python /src/scripts/fs/test_fs1134_telemetry_integration.py
'
