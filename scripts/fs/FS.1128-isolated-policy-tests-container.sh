#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
echo "FS1128_MODE=ISOLATED_POLICY_REGRESSIONS_WITH_DEPENDENCIES"
echo "FS1128_PRODUCTION_MUTATION=NONE"
echo "FS1128_LIVE_REMEDIATION=NONE"
echo "FS1128_COMMIT=$(git -C "$ROOT" rev-parse --short HEAD)"
echo "FS1128_IMAGE=python:3.12-slim"
docker run --rm -i --network bridge --mount "type=bind,source=$ROOT,target=/src,readonly" -w /src -e PYTHONDONTWRITEBYTECODE=1 python:3.12-slim sh -ec '
 python -m pip install --disable-pip-version-check --quiet "fastapi>=0.110,<1" "pydantic>=2,<3"
 python tests/test_incident_explorer_v285.py
 python tests/test_incident_catalog_v286.py
 python tests/test_policy_control_api_v2103.py
 python tests/test_policy_simulation_api_v2105.py
'
echo "FS1128_RESULT=ALL_FOUR_SUITES_PASS"
