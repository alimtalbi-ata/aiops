#!/usr/bin/env python3
"""Host-only, single-instance coordinator. No service/cron or production mutations."""
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[4]
RUN = ROOT.parent / 'runtime'
DEADLINE = dt.datetime(2026, 11, 10, 11, tzinfo=ZoneInfo('Europe/Paris')).timestamp()
INTERVAL = 600
CYCLE_LIMIT = 540
LOCK = Path('/tmp/aiops2-night-20261109.lock')
STOP = RUN / 'STOP'

def save(**fields):
    RUN.mkdir(parents=True, exist_ok=True)
    state = {}
    if (RUN / 'state.json').exists():
        state = json.loads((RUN / 'state.json').read_text())
    state.update(fields, updated_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                 deadline=dt.datetime.fromtimestamp(DEADLINE, ZoneInfo('Europe/Paris')).isoformat())
    tmp = RUN / 'state.tmp'
    tmp.write_text(json.dumps(state, indent=2) + '\n')
    tmp.replace(RUN / 'state.json')
    with (RUN / 'supervisor.log').open('a') as log:
        log.write(json.dumps(state) + '\n')

def host_blocker():
    status = Path('/proc/self/status').read_text()
    if any(line.split() == ['NoNewPrivs:', '1'] for line in status.splitlines()):
        return 'NoNewPrivs=1: refusing nested sandbox; run from host terminal'
    if os.environ.get('CODEX_SANDBOX') or Path('/.flatpak-info').exists():
        return 'Sandbox marker present: host context required'
    return None

def kill_group(child):
    if child is not None:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait()

def run():
    RUN.mkdir(parents=True, exist_ok=True)
    with LOCK.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('Already locked; no second supervisor started', file=sys.stderr)
            return 73
        if time.time() >= DEADLINE:
            save(status='expired', supervisor_pid=None, child_pid=None)
            return 0
        blocker = host_blocker()
        if blocker:
            save(status='blocked_host_context', reason=blocker, supervisor_pid=None,
                 child_pid=None, first_cycle='NOT_STARTED')
            print(blocker, file=sys.stderr)
            return 78
        if STOP.exists():
            print('STOP exists; explicit removal required before restart', file=sys.stderr)
            return 0
        stopped = False
        def stop_handler(*_):
            nonlocal stopped
            stopped = True
        signal.signal(signal.SIGTERM, stop_handler)
        signal.signal(signal.SIGINT, stop_handler)
        previous = json.loads((RUN / 'state.json').read_text()) if (RUN / 'state.json').exists() else {}
        cycle = previous.get('cycle', 0)
        child = None
        save(status='running', supervisor_pid=os.getpid(), child_pid=None)
        try:
            while not stopped and not STOP.exists() and time.time() < DEADLINE:
                cycle += 1
                start = time.monotonic()
                prefix = RUN / f'cycle-{cycle:04d}'
                command = ['timeout', '--signal=KILL', str(min(CYCLE_LIMIT, max(0.1, DEADLINE - time.time() - 1))), 'codex', '-a', 'never', 'exec', '--sandbox', 'workspace-write',
                           '-c', 'sandbox_workspace_write.network_access=true',
                           '-C', str(ROOT), '--add-dir', str(RUN), '--json',
                           '-o', str(prefix) + '-result.md', '-']
                with (Path(str(prefix) + '.jsonl')).open('a') as output, \
                     (Path(__file__).with_name('mission.md')).open() as prompt:
                    child = subprocess.Popen(command, stdin=prompt, stdout=output,
                                             stderr=subprocess.STDOUT, start_new_session=True,
                                             pass_fds=(lock.fileno(),))
                    save(status='cycle_running', cycle=cycle, child_pid=child.pid,
                         command=command, cycle_log=str(prefix) + '.jsonl',
                         **({'first_cycle': 'RUNNING'} if cycle == 1 else {}))
                    reason = 'completed'
                    while child.poll() is None:
                        if time.time() >= DEADLINE:
                            reason = 'deadline'; break
                        if stopped or STOP.exists():
                            reason = 'operator_stop'; break
                        if time.monotonic() - start >= CYCLE_LIMIT:
                            reason = 'cycle_timeout'; break
                        time.sleep(min(0.2, max(0, DEADLINE - time.time())))
                    kill_group(child)  # also remove surviving descendants after normal exit
                    code = child.returncode
                    if reason == 'completed' and code != 0:
                        reason = 'child_failed_or_timed_out'
                    child = None
                    save(status='waiting', cycle=cycle, child_pid=None,
                         last_exit=code, last_cycle_reason=reason,
                         last_cycle_completed=(reason == 'completed'),
                         **({'first_cycle': 'COMPLETED' if reason == 'completed' else 'FAILED_OR_INTERRUPTED'} if cycle == 1 else {}))
                if reason in ('deadline', 'operator_stop'):
                    break
                while time.monotonic() - start < INTERVAL:
                    if stopped or STOP.exists() or time.time() >= DEADLINE:
                        break
                    time.sleep(min(0.2, max(0, DEADLINE - time.time())))
        finally:
            kill_group(child)
            save(status='expired' if time.time() >= DEADLINE else 'stopped',
                 supervisor_pid=None, child_pid=None)
    return 0

if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv) > 1 else 'run'
    RUN.mkdir(parents=True, exist_ok=True)
    if action == 'stop':
        STOP.touch()
        print('Stop requested; active child group killed within 0.2 seconds')
    elif action == 'start':
        # Guard in foreground too; never detach a nested Codex launcher.
        if host_blocker() or time.time() >= DEADLINE:
            sys.exit(run())
        with (RUN / 'launcher.log').open('a') as out:
            proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'run'],
                                    stdin=subprocess.DEVNULL, stdout=out, stderr=out,
                                    start_new_session=True)
        print(f'Launch requested PID {proc.pid}; verify state.json and process before claiming active')
    elif action == 'run':
        sys.exit(run())
    else:
        raise SystemExit('Usage: supervisor.py [start|run|stop]')
