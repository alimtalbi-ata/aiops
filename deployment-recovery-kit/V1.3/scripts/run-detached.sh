#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
SELF_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
OUT=/home/aiops/aiops2-reconstruction/reports
mkdir -p "$OUT"; chmod 700 "$OUT"
LOG="$OUT/collector.log"
nohup "$SELF_DIR/collect-runtime.sh" >"$LOG" 2>&1 </dev/null &
echo "PID=$!"; echo "LOG=$LOG"; echo "SSH_DISCONNECT_SAFE=YES"
