#!/usr/bin/env bash
set -euo pipefail
echo "FS1053_MODE=AUTHORIZED_PRODUCTION_REPLACEMENT"
python3 "$(dirname "$0")/fs1053_native_deploy.py"
