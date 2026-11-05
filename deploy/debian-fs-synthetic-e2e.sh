#!/usr/bin/env bash
# Explicit, synthetic-only end-to-end filesystem demo. No cron, GLPI, Docker or real mount.
set -Eeuo pipefail
umask 077
[[ "$(id -un)" == aiops ]] || { echo "FAIL_CLOSED: aiops user required" >&2; exit 78; }
[[ "$(hostname -s | tr '[:upper:]' '[:lower:]')" == srv-deb-05 ]] || { echo "FAIL_CLOSED: host mismatch" >&2; exit 78; }
[[ -z "${AIOPS_FS_DEMO_TEST_ROOT:-}" && -z "${AIOPS_FS_DEMO_TEST_MODE:-}" ]] || {
  echo "FAIL_CLOSED: test overrides forbidden on host" >&2; exit 78;
}
[[ "$#" -eq 1 && "$1" =~ ^FS-[A-Za-z0-9_-]{1,60}$ ]] || {
  echo "Usage: $0 FS-unique-run-id" >&2; exit 78;
}
run_id="$1"
dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
root=/home/aiops/.local/state/aiops2-demo-filesystem
[[ ! -L "$root" && ! -L "$root/runs" && ! -L "$root/remediation" ]] || {
  echo "FAIL_CLOSED: symlink state root" >&2; exit 78;
}
[[ -f "$dir/aiops2-mini-filesystem-demo.sh" && ! -L "$dir/aiops2-mini-filesystem-demo.sh" ]] || exit 78
[[ -f "$dir/debian-fs-synthetic-cycle.sh" && ! -L "$dir/debian-fs-synthetic-cycle.sh" ]] || exit 78
[[ -f "$dir/fs_demo.py" && ! -L "$dir/fs_demo.py" ]] || exit 78
[[ ! -e "$root/remediation/$run_id" && ! -L "$root/remediation/$run_id" ]] || {
  echo "FAIL_CLOSED: remediation run already exists" >&2; exit 78;
}
# Only synthetic sparse-file operations; existing remediation cycle validates mitigation and rollback.
/bin/bash "$dir/aiops2-mini-filesystem-demo.sh"
latest="$root/runs/latest"
[[ -L "$latest" ]] || { echo "FAIL_CLOSED: no detection pointer" >&2; exit 78; }
/usr/bin/python3 - "$root" <<'PY'
import hashlib, json, pathlib, sys
root=pathlib.Path(sys.argv[1])
runs=root/'runs'
latest=runs/'latest'
name=latest.readlink()
if name.is_absolute() or len(name.parts)!=1 or name.name in ('.','..'):
    raise SystemExit('FAIL_CLOSED: unsafe latest pointer')
run=runs/name
if run.is_symlink() or not run.is_dir():
    raise SystemExit('FAIL_CLOSED: invalid detection run')
for filename in ('metadata.txt','metrics.csv','incident.json','status.txt'):
    p=run/filename
    if p.is_symlink() or not p.is_file():
        raise SystemExit('FAIL_CLOSED: unsafe detection artifact')
lines=(run/'SHA256SUMS').read_text().splitlines()
expected={}
for line in lines:
    digest, sep, name=line.partition('  ')
    if not sep or name not in ('metadata.txt','metrics.csv','incident.json','status.txt') or name in expected:
        raise SystemExit('FAIL_CLOSED: invalid SHA256SUMS')
    expected[name]=digest
if len(expected)!=4 or any(hashlib.sha256((run/name).read_bytes()).hexdigest()!=digest for name,digest in expected.items()):
    raise SystemExit('FAIL_CLOSED: detection checksum mismatch')
incident=json.loads((run/'incident.json').read_text())
if not (incident.get('state')=='DETECTED_SIMULATED' and
        incident.get('logical_used_mib')==11 and
        incident.get('logical_capacity_mib')==12 and
        incident.get('threshold_pct')==75 and
        incident.get('live_effect') is False and
        incident.get('glpi_ticket') is None and
        incident.get('temporal_workflow') is None):
    raise SystemExit('FAIL_CLOSED: invalid synthetic incident')
print('FS_DETECTION=PASS')
print('FS_DETECTION_RUN='+str(name))
PY
/bin/bash "$dir/debian-fs-synthetic-cycle.sh" "$run_id"
echo "FS_END_TO_END=PASS_SYNTHETIC_LOCAL_ONLY"
echo "FS_REMEDIATION_RUN=$run_id"
echo "FS_PUBLICATION=NOT_YET_VERIFIED"
