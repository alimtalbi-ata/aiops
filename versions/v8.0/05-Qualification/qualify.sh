#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$ROOT/05-Qualification/contract_audit.py"
bash -n "$ROOT/05-Qualification/qualify.sh"
bash -n "$ROOT/05-Qualification/retire-legacy.sh"
python3 -m py_compile "$ROOT/05-Qualification/contract_audit.py"
echo "STATIC_QUALIFICATION=PASS"
echo "RUNTIME_QUALIFICATION=REQUIRED_ON_TARGET_VM"
