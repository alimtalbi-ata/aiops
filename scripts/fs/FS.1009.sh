#!/usr/bin/env bash
set -euo pipefail

echo '===== FS.1009 | TWIN DECIMAL METRICS CANDIDATE BUILD ====='
REPO=/home/aiops/aiops2-v2-delivery
CONTAINER=aiops2-rebuild-twin
CANDIDATE_IMAGE=aiops2-twin:fs1009-decimal-metrics-candidate-20261106
TMP="$(mktemp -d /tmp/fs1009.XXXXXXXX)"
trap 'rm -rf "$TMP"' EXIT

command -v docker >/dev/null
docker inspect "$CONTAINER" >/dev/null
BASE_IMAGE="$(docker inspect --format '{{.Config.Image}}' "$CONTAINER")"
BASE_CONTAINER_IMAGE_ID="$(docker inspect --format '{{.Image}}' "$CONTAINER")"
test -n "$BASE_IMAGE"

echo "SOURCE_CONTAINER=$CONTAINER"
echo "BASE_IMAGE=$BASE_IMAGE"
echo '===== EXTRACT RUNTIME MODULE (READ ONLY) ====='
docker cp "$CONTAINER:/app/twin/fs_observations.py" "$TMP/fs_observations.py" >/dev/null
test -s "$TMP/fs_observations.py"

echo '===== APPLY NARROW DECIMAL VALIDATION PATCH ====='
python3 - "$TMP/fs_observations.py" <<'PY'
import ast
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
source = path.read_text()
tree = ast.parse(source)

matches = [
    n for n in tree.body
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    and n.name == "fs_lab_metrics"
]
assert len(matches) == 1, "expected exactly one fs_lab_metrics function"
assert "if type(value) not in (int, float):" in source, "runtime source differs from FS.1005/FS.1008 baseline"
assert source.count("if type(value) not in (int, float):") == 1
assert "def _validated_fs_percent(" not in source, "patch already present; refusing ambiguous reapplication"

imports = []
if not any(
    isinstance(n, ast.Import) and any(a.name == "math" for a in n.names)
    for n in tree.body
):
    imports.append("import math\n")
if not any(
    isinstance(n, ast.ImportFrom)
    and n.module == "decimal"
    and any(a.name == "Decimal" for a in n.names)
    for n in tree.body
):
    imports.append("from decimal import Decimal\n")

lines = source.splitlines(keepends=True)
insert_after = 0
for node in tree.body:
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
        insert_after = max(insert_after, node.end_lineno)
    elif isinstance(node, ast.ImportFrom) and node.module == "__future__":
        insert_after = max(insert_after, node.end_lineno)
if imports:
    lines[insert_after:insert_after] = imports
source = "".join(lines)

tree = ast.parse(source)
fn = next(
    n for n in tree.body
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    and n.name == "fs_lab_metrics"
)
decorator_line = min((d.lineno for d in fn.decorator_list), default=fn.lineno)
lines = source.splitlines(keepends=True)
helper = (
    "def _validated_fs_percent(value):\n"
    "    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):\n"
    "        raise ValueError('invalid_observation_value')\n"
    "    numeric_value = float(value)\n"
    "    if not math.isfinite(numeric_value) or not 0 <= numeric_value <= 100:\n"
    "        raise ValueError('invalid_observation_value')\n"
    "    return numeric_value\n\n\n"
)
lines[decorator_line - 1:decorator_line - 1] = [helper]
source = "".join(lines)

old_guard = (
    "    if type(value) not in (int, float):\n"
    "        raise HTTPException(503, \"invalid_observation_value\")\n"
    "\n"
    "    if not 0 <= value <= 100:\n"
    "        raise HTTPException(503, \"invalid_observation_value\")"
)
new_guard = (
    "    try:\n"
    "        numeric_value = _validated_fs_percent(value)\n"
    "    except (TypeError, ValueError, OverflowError):\n"
    "        raise HTTPException(503, \"invalid_observation_value\")"
)
assert source.count(old_guard) == 1, "numeric guard block differs; refusing fuzzy patch"
source = source.replace(old_guard, new_guard, 1)

old_firing = "    firing = 1 if value >= THRESHOLD else 0"
assert source.count(old_firing) == 1, "firing expression differs"
source = source.replace(old_firing, "    firing = 1 if numeric_value >= THRESHOLD else 0", 1)

old_metric = '        f"aiops_twin_fs_lab_used_percent{labels} {value}\\n"'
assert source.count(old_metric) == 1, "filesystem metric exposition differs"
source = source.replace(
    old_metric,
    '        f"aiops_twin_fs_lab_used_percent{labels} {numeric_value}\\n"',
    1,
)

ast.parse(source)
assert "isinstance(value, bool)" in source
assert "math.isfinite(numeric_value)" in source
assert "numeric_value >= THRESHOLD" in source
assert "{numeric_value}\\n" in source
path.write_text(source)
print("PATCHED_SOURCE=PASS")
print("DECIMAL_ACCEPTED=YES")
print("BOOL_REJECTED=YES")
print("NONFINITE_REJECTED=YES")
print("RANGE_CHECK=0..100")
PY

echo '===== SOURCE COMPILE ====='
python3 -m py_compile "$TMP/fs_observations.py"
sha256sum "$TMP/fs_observations.py" | awk '{print "PATCHED_SOURCE_SHA256=" $1}'

cat > "$TMP/Dockerfile" <<'DOCKER'
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
COPY fs_observations.py /app/twin/fs_observations.py
RUN python -m py_compile /app/twin/fs_observations.py
DOCKER

echo '===== BUILD ISOLATED CANDIDATE IMAGE ====='
docker build --build-arg "BASE_IMAGE=$BASE_IMAGE" -t "$CANDIDATE_IMAGE" "$TMP"

echo '===== CANDIDATE PURE CONTRACT TESTS ====='
docker run --rm -i --entrypoint python -w /app "$CANDIDATE_IMAGE" - <<'PY'
from decimal import Decimal
from twin.fs_observations import _validated_fs_percent

accepted = [
    (Decimal("92"), 92.0),
    (Decimal("0"), 0.0),
    (Decimal("100"), 100.0),
    (92, 92.0),
    (92.0, 92.0),
]
for value, expected in accepted:
    actual = _validated_fs_percent(value)
    assert actual == expected, (value, actual, expected)
    print(f"ACCEPT={type(value).__name__}:{value} -> {actual}")

rejected = [
    True, False,
    Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity"),
    float("nan"), float("inf"), float("-inf"),
    Decimal("-0.01"), Decimal("100.01"),
    -1, 101,
    "92", None,
]
for value in rejected:
    try:
        _validated_fs_percent(value)
    except (TypeError, ValueError, OverflowError):
        print(f"REJECT={type(value).__name__}:{value}")
    else:
        raise AssertionError(f"unexpectedly accepted {value!r}")
print("FS1009_CONTRACT_CASES=19")
print("FS1009_CONTRACT_RESULT=PASS")
PY

echo '===== IMAGE AND SOURCE INTEGRITY ====='
docker image inspect "$CANDIDATE_IMAGE" --format 'CANDIDATE_IMAGE_ID={{.Id}}'
AFTER_CONTAINER_IMAGE_ID="$(docker inspect --format '{{.Image}}' "$CONTAINER")"
test "$AFTER_CONTAINER_IMAGE_ID" = "$BASE_CONTAINER_IMAGE_ID"
echo "BASE_CONTAINER_IMAGE_UNCHANGED=YES"
echo "CANDIDATE_IMAGE=$CANDIDATE_IMAGE"
echo 'METRICS_ENDPOINT_E2E=NOT_RUN'
echo 'TWIN_SERVICE_STARTED=NO'
echo 'PRODUCTION_RESTARTED=NO'
echo 'DATABASE_WRITES=0'
echo 'HTTP_WRITES=0'
echo '===== END FS.1009 ====='
