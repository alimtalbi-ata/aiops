#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
echo "FS1127_MODE=ISOLATED_FUNCTIONAL_REGRESSION_TESTS"
echo "FS1127_COMMIT=$(git rev-parse --short HEAD)"
echo "FS1127_PRODUCTION_MUTATION=NONE"
echo "FS1127_LIVE_REMEDIATION=DISABLED"
python3 - <<'PY'
import importlib.util
for name in ("fastapi","pydantic"):
 print("DEPENDENCY_%s=%s"%(name,"PRESENT" if importlib.util.find_spec(name) else "MISSING"))
PY
fail=0
run_test() {
  local label="$1" path="$2"
  echo "=== TEST $label ==="
  if python3 "$path"; then
    echo "TEST_RESULT=$label PASS"
  else
    rc=$?
    echo "TEST_RESULT=$label FAIL_OR_DEPENDENCY_MISSING exit=$rc"
    fail=$((fail+1))
  fi
}
run_test INCIDENT_EXPLORER tests/test_incident_explorer_v285.py
run_test INCIDENT_CATALOG tests/test_incident_catalog_v286.py
run_test POLICY_CONTROL tests/test_policy_control_api_v2103.py
run_test POLICY_SIMULATION tests/test_policy_simulation_api_v2105.py
echo "FS1127_FAILED_GROUPS=$fail"
if [ "$fail" -gt 0 ]; then
 echo "FS1127_RESULT=NEEDS_ANALYSIS"
 exit 1
fi
echo "FS1127_RESULT=ALL_ISOLATED_GROUPS_PASS"
