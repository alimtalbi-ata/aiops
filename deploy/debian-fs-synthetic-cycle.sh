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
"$py" "$dir/fs_demo.py" init --run-id "$run_id"
"$py" "$dir/fs_demo.py" propose --run-id "$run_id"
"$py" "$dir/fs_demo.py" cleanup-logs --run-id "$run_id" --approval SYNTHETIC_APPROVED
"$py" "$dir/fs_demo.py" rollback --run-id "$run_id" --approval SYNTHETIC_APPROVED
"$py" - "$run_id" <<'PY'
import hashlib, json, pathlib, sys
rid = sys.argv[1]
p = pathlib.Path('/home/aiops/.local/state/aiops2-demo-filesystem/remediation') / rid
if any(q.is_symlink() for q in (p, p/'state.json', p/'receipt.json')):
    raise SystemExit('FAIL_CLOSED: symlink')
raw = (p/'state.json').read_bytes()
s, r = json.loads(raw), json.loads((p/'receipt.json').read_bytes())
assert s['run_id'] == r['run_id'] == rid
assert (s['phase'], s['incident'], s['used_mib'], s['capacity_mib'],
        s['logs_mib'], s['rollback_closed'], s['action']) == (
        'OPEN', 'OPEN_SIMULATED', 11, 12, 5, True, None)
assert r['command'] == 'rollback' and r['synthetic_only'] is True and r['live_effects'] is False
assert r['state_sha256'] == hashlib.sha256(raw).hexdigest()
print('FS_SYNTHETIC_ROLLBACK=PASS')
print('RUN_ID=' + rid)
print('STATE_SHA256=' + r['state_sha256'])
PY
