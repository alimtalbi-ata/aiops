#!/usr/bin/env bash
# Synthetic-only lifecycle; source-only until reviewed for existing Debian poller.
set -Eeuo pipefail
umask 077
[[ "$(id -un)" == aiops ]] || { echo "FAIL_CLOSED: aiops required" >&2; exit 2; }
[[ "$#" -eq 1 && "$1" =~ ^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$ ]] || { echo "FAIL_CLOSED: run-id" >&2; exit 2; }
run_id="$1"
dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
[[ -f "$dir/fs_demo.py" && ! -L "$dir/fs_demo.py" ]] || exit 2
py=/usr/bin/python3
# Best-effort rollback on any failure after an action is applied. Never hide the original error.
action_applied=0
on_exit() {
  local code=$?
  trap - EXIT
  if (( code != 0 && action_applied == 1 )); then
    "$py" "$dir/fs_demo.py" rollback --run-id "$run_id" --approval SYNTHETIC_APPROVED >&2 ||
      echo "FAIL_CLOSED: automatic synthetic rollback failed; manual review required" >&2
  fi
  exit "$code"
}
trap on_exit EXIT
"$py" "$dir/fs_demo.py" init --run-id "$run_id"
"$py" "$dir/fs_demo.py" propose --run-id "$run_id"
"$py" "$dir/fs_demo.py" cleanup-logs --run-id "$run_id" --approval SYNTHETIC_APPROVED
action_applied=1
"$py" "$dir/fs_demo.py" status --run-id "$run_id"
"$py" - "$run_id" ACTION_APPLIED <<'PY'
import json, pathlib, sys
rid, expected = sys.argv[1:]
p = pathlib.Path('/home/aiops/.local/state/aiops2-demo-filesystem/remediation') / rid
s = json.loads((p/'state.json').read_bytes())
if not (s.get('run_id') == rid and s.get('phase') == expected and
        s.get('incident') == 'MITIGATED_SIMULATED' and
        s.get('used_mib') == 6 and s.get('capacity_mib') == 12 and
        s.get('logs_mib') == 0 and s.get('rollback_closed') is False and
        s.get('action') == 'cleanup-logs'):
    raise SystemExit('FAIL_CLOSED: applied state mismatch')
print('FS_SYNTHETIC_MITIGATION=PASS')
PY
"$py" "$dir/fs_demo.py" rollback --run-id "$run_id" --approval SYNTHETIC_APPROVED
action_applied=0
"$py" - "$run_id" <<'PY'
import hashlib, json, pathlib, sys
rid = sys.argv[1]
p = pathlib.Path('/home/aiops/.local/state/aiops2-demo-filesystem/remediation') / rid
if any(q.is_symlink() for q in (p, p/'state.json', p/'receipt.json')):
    raise SystemExit('FAIL_CLOSED: symlink')
raw = (p/'state.json').read_bytes()
s, r = json.loads(raw), json.loads((p/'receipt.json').read_bytes())
if not (s.get('run_id') == r.get('run_id') == rid and
        (s.get('phase'), s.get('incident'), s.get('used_mib'), s.get('capacity_mib'),
         s.get('logs_mib'), s.get('rollback_closed'), s.get('action')) ==
        ('OPEN', 'OPEN_SIMULATED', 11, 12, 5, True, None) and
        r.get('command') == 'rollback' and r.get('synthetic_only') is True and
        r.get('live_effects') is False and
        r.get('state_sha256') == hashlib.sha256(raw).hexdigest()):
    raise SystemExit('FAIL_CLOSED: rollback state or receipt mismatch')
print('FS_SYNTHETIC_ROLLBACK=PASS')
print('RUN_ID=' + rid)
print('STATE_SHA256=' + r['state_sha256'])
PY
