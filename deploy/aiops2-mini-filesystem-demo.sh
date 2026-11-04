#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
ROOT=/home/aiops/.local/state/aiops2-demo-filesystem
CAPACITY_MIB=12
THRESHOLD_PCT=75
INCIDENT_ID=DEMO-FS-001
[[ "$(id -un)" == aiops ]] || { echo "Run as aiops" >&2; exit 2; }
[[ ! -L "$ROOT" ]] || { echo "Refusing symlink root" >&2; exit 2; }
mkdir -p -- "$ROOT"
[[ "$(realpath -e "$ROOT")" == "$ROOT" ]] || exit 2
[[ ! -L "$ROOT/runs" ]] || exit 2
mkdir -p -- "$ROOT/runs"
RUN_ID="FS-$(date -u +%Y%m%dT%H%M%SZ)-$$"
RUN="$ROOT/runs/$RUN_ID"
mkdir -- "$RUN"
printf 'run_id=%s\nincident_id=%s\nroot=%s\n' "$RUN_ID" "$INCIDENT_ID" "$ROOT" > "$RUN/metadata.txt"
printf 'timestamp_utc,step,used_mib,capacity_mib,usage_pct,state\n' > "$RUN/metrics.csv"
for used in 2 4 7 10 11; do
  step=$(( ${step:-0} + 1 ))
  truncate -s "${used}M" -- "$RUN/payload.img"
  pct=$((used*100/CAPACITY_MIB))
  state=OK
  (( pct >= THRESHOLD_PCT )) && state=ALERT
  printf '%s,%d,%d,%d,%d,%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$step" "$used" "$CAPACITY_MIB" "$pct" "$state" >> "$RUN/metrics.csv"
  sleep 1
done
cat > "$RUN/incident.json" <<JSON
{
  "incident_id": "$INCIDENT_ID",
  "run_id": "$RUN_ID",
  "source": "synthetic_debian_mini_filesystem",
  "path": "$RUN/payload.img",
  "logical_capacity_mib": 12,
  "logical_used_mib": 11,
  "logical_usage_pct": 91,
  "threshold_pct": 75,
  "severity": "WARNING",
  "state": "DETECTED_SIMULATED",
  "live_effect": false,
  "glpi_ticket": null,
  "core_authorization": null,
  "temporal_workflow": null,
  "evidence_type": "local_synthetic_only"
}
JSON
printf 'DETECTED_SIMULATED\n' > "$RUN/status.txt"
(cd "$RUN" && sha256sum metadata.txt metrics.csv incident.json status.txt > SHA256SUMS && sha256sum -c SHA256SUMS)
ln -s -- "$RUN_ID" "$ROOT/runs/latest.tmp.$$"
mv -Tf -- "$ROOT/runs/latest.tmp.$$" "$ROOT/runs/latest"
printf 'DEMO_RESULT=PASS_SYNTHETIC_LOCAL_ONLY\nRUN_DIR=%s\n' "$RUN"
