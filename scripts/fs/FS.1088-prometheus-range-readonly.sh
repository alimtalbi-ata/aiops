#!/usr/bin/env bash
set -euo pipefail
echo "FS1088_MODE=READ_ONLY_PROMETHEUS_QUERY_RANGE"
python3 "$(dirname "$0")/fs1088_prometheus_range_audit.py"
