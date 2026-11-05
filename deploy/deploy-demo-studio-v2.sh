#!/usr/bin/env bash
# Existing Debian poll.sh executes this on a new stable SHA; no new cron or stack.
set -Eeuo pipefail
umask 077
delivery="$(cd "$(dirname "$0")/.." && pwd)"
state=/home/aiops/.local/state/aiops-debian-agent
# A previous PASS cannot qualify a later failed or unexecuted job.
rm -f "$state/portal-deploy-result.json" "$state/portal-compose-result.json" "$state/portal-host-contracts.json" "$state/acme-sim-e2e.json"
status=0
# An E2E-only stable SHA must not rebuild/recreate the already healthy portal.
# Portal deployment is an explicit, separately pinned release intent.
portal_enabled="$(/usr/bin/python3 - "$delivery/deploy/debian-portal-release.json" <<'PY'
import json,sys
try:
 print('yes' if json.load(open(sys.argv[1]))['enabled'] is True else 'no')
except (OSError,ValueError,KeyError,TypeError):
 print('invalid')
PY
)"
if [ "$portal_enabled" = yes ]; then
  /bin/bash "$delivery/deploy/debian-portal-deploy.sh" || status=$?
  if [ "$status" -eq 0 ]; then
    /usr/bin/python3 "$delivery/deploy/debian-portal-canonicalize.py" || status=$?
    if [ "$status" -eq 0 ]; then
      /usr/bin/python3 "$delivery/deploy/debian-portal-ux-contracts.py" || status=$?
    fi
  fi
elif [ "$portal_enabled" != no ]; then
  status=78
fi
# Anonymous, read-only host tests run even if upgrade was blocked; never promote E2E.
/usr/bin/python3 "$delivery/deploy/debian-portal-host-contracts.py" || status=78
# P0 T1: one-shot anonymous Chromium ON DEBIAN via the existing stable poller.
# This is read-only and non-blocking for Core/ACME; FAIL remains NO_GO in its
# private receipt and in the sanitized preflight report. Never upload PNGs.
if [ "$status" -eq 0 ]; then
  # P0 #396: the first real host attempt proved ModuleNotFoundError. Bootstrap
  # Playwright 1.55.0 + its Chromium headless shell in the aiops USER state,
  # never apt/sudo/system Python. Existing cron flock serializes this one-shot.
  playwright_dir="$state/portal-playwright"
  playwright_python="$playwright_dir/venv/bin/python"
  export PLAYWRIGHT_BROWSERS_PATH="$playwright_dir/browsers"
  host_short="$(/bin/hostname -s | /usr/bin/tr '[:upper:]' '[:lower:]')"
  if [ "$host_short" = "srv-deb-05" ] && [ ! -L "$playwright_dir" ]; then
    /bin/mkdir -p "$playwright_dir"
    /bin/chmod 700 "$playwright_dir"
    if [ ! -x "$playwright_python" ]; then
      /usr/bin/timeout 60 /usr/bin/python3 -m venv "$playwright_dir/venv" \
        >/dev/null 2>&1 || echo "HOST_PLAYWRIGHT_BOOTSTRAP_VENV_FAILED"
    fi
    if [ -x "$playwright_python" ]; then
      if ! "$playwright_python" -c 'import playwright' >/dev/null 2>&1; then
        /usr/bin/timeout 180 "$playwright_python" -m pip install \
          --disable-pip-version-check --no-input --no-cache-dir playwright==1.55.0 \
          >/dev/null 2>&1 || echo "HOST_PLAYWRIGHT_BOOTSTRAP_PIP_FAILED"
      fi
      /usr/bin/timeout 240 "$playwright_python" -m playwright install \
        chromium --only-shell >/dev/null 2>&1 || \
        echo "HOST_PLAYWRIGHT_BOOTSTRAP_CHROMIUM_FAILED"
    fi
  else
    echo "HOST_PLAYWRIGHT_BOOTSTRAP_HOST_OR_PATH_REJECTED"
  fi
  if [ ! -x "$playwright_python" ]; then
    playwright_python=/usr/bin/python3
  fi
  /usr/bin/timeout 180 "$playwright_python" \
    "$delivery/deploy/debian-portal-playwright-snapshot.py" \
    --base-url http://127.0.0.1:7777 --assert-host SRV-DEB-05 \
    --output-dir "$playwright_dir" || echo "HOST_PLAYWRIGHT_NOT_VERIFIED"
fi
# Optional five-service ACME sandbox in-place upgrade. Default disabled.
acme_enabled="$(/usr/bin/python3 - "$delivery/deploy/debian-acme-sandbox-release.json" <<'PY'
import json,sys
try: print('yes' if json.load(open(sys.argv[1]))['enabled'] is True else 'no')
except (OSError,ValueError,KeyError,TypeError): print('invalid')
PY
)"
if [ "$acme_enabled" = yes ] && [ "$status" -eq 0 ]; then
  /bin/bash "$delivery/deploy/debian-acme-sandbox-upgrade.sh" || status=78
elif [ "$acme_enabled" = invalid ]; then
  status=78
fi
# Synthetic E2E uses only the existing containers and never calls real GLPI.
# Missing sandbox capabilities yield a BLOCKED receipt without any POST.
if [ "$status" -eq 0 ]; then
  /usr/bin/python3 "$delivery/deploy/debian-acme-sim-e2e.py" || status=78
fi
# Optional filesystem-only synthetic cycle. OFF by default; never touch Compose/GLPI.
# Existing stable poller/flock provides serialization. This hook does not add cron.
fs_manifest="$delivery/deploy/debian-fs-synthetic-release.json"
fs_args="$(/usr/bin/python3 - "$fs_manifest" <<'PY'
import json,re,sys
try:
 with open(sys.argv[1],encoding='utf-8') as f:
  data=json.load(f)
 assert data.get('schema')=='aiops.fs-synthetic-release.v1'
 if data.get('enabled') is False:
  print('DISABLED')
 elif (data.get('enabled') is True and
       data.get('mode')=='SYNTHETIC_NO_LIVE_EFFECTS' and
       data.get('host')=='srv-deb-05' and
       data.get('approval')=='SYNTHETIC_APPROVED' and
       re.fullmatch(r'[a-f0-9]{40}',data.get('source_commit','')) and
       re.fullmatch(r'FS-[A-Za-z0-9_-]{1,60}',data.get('run_id',''))):
  print(data['source_commit']+' '+data['run_id'])
 else:
  print('INVALID')
except (OSError,ValueError,TypeError,AssertionError):
 print('INVALID')
PY
)"
if [ "$fs_args" = INVALID ]; then
  echo "FS_SYNTHETIC=FAIL_CLOSED_MANIFEST"
  status=78
elif [ "$fs_args" != DISABLED ]; then
  read -r fs_source fs_run <<< "$fs_args"
  fs_host="$(/bin/hostname -s | /usr/bin/tr '[:upper:]' '[:lower:]')"
  fs_root=/home/aiops/.local/state/aiops2-demo-filesystem
  fs_marker="$fs_root/remediation/$fs_run/receipt.json"
  if [ "$fs_host" != srv-deb-05 ] || [ "$(id -un)" != aiops ]; then
    echo "FS_SYNTHETIC=FAIL_CLOSED_HOST"
    status=78
  elif [ -e "$fs_marker" ] || [ -L "$fs_marker" ]; then
    # An already-used run ID is never replayed or misreported as fresh.
    echo "FS_SYNTHETIC=ALREADY_ATTEMPTED"
  elif ! /usr/bin/git -C "$delivery" cat-file -e "$fs_source^{commit}" 2>/dev/null ||
       ! /usr/bin/git -C "$delivery" show "$fs_source:deploy/fs_demo.py" |
          /usr/bin/cmp -s - "$delivery/deploy/fs_demo.py" ||
       ! /usr/bin/git -C "$delivery" show "$fs_source:deploy/debian-fs-synthetic-cycle.sh" |
          /usr/bin/cmp -s - "$delivery/deploy/debian-fs-synthetic-cycle.sh" ||
       ! /usr/bin/git -C "$delivery" show "$fs_source:deploy/aiops2-mini-filesystem-demo.sh" |
          /usr/bin/cmp -s - "$delivery/deploy/aiops2-mini-filesystem-demo.sh" ||
       ! /usr/bin/git -C "$delivery" show "$fs_source:deploy/debian-fs-synthetic-e2e.sh" |
          /usr/bin/cmp -s - "$delivery/deploy/debian-fs-synthetic-e2e.sh"; then
    echo "FS_SYNTHETIC=FAIL_CLOSED_SOURCE_DRIFT"
    status=78
  elif [ -n "${AIOPS_FS_DEMO_TEST_ROOT:-}" ] || [ -n "${AIOPS_FS_DEMO_TEST_MODE:-}" ]; then
    echo "FS_SYNTHETIC=FAIL_CLOSED_TEST_ENV"
    status=78
  elif /usr/bin/timeout 90 /bin/bash "$delivery/deploy/debian-fs-synthetic-e2e.sh" "$fs_run"; then
    echo "FS_SYNTHETIC=PASS_LOCAL_RECEIPT_PENDING_PUBLICATION"
  else
    echo "FS_SYNTHETIC=FAIL_CLOSED_EXECUTION"
    status=78
  fi
fi

/usr/bin/python3 "$delivery/deploy/debian-portal-preflight.py" || status=78
exit "$status"
