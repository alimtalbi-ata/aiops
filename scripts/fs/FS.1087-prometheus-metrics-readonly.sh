#!/usr/bin/env bash
set -euo pipefail
echo "FS1087_MODE=READ_ONLY_PROMETHEUS_METRICS_DISCOVERY"
python3 "$(dirname "$0")/fs1087_prometheus_discovery.py"
