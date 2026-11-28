"""Disposable CI only: compare a restored POC backup with its quiesced source."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from poc_restore_check import verify_restore
from pocctl import Lifecycle

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'release-lab'))
from e17_pg_restore import snapshot

WRITERS = ('core', 'twin', 'evidence', 'policy')
CI_ROOT = Path('/tmp/aiops-v3-rootless-ci')


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def prove(ctl, *, project_snapshot=snapshot, restore=verify_restore):
    """Stop the four application writers; only read the source PostgreSQL."""
    require(not ctl.orchestration, 'default POC profile required')
    ctl.health()
    # The CI runner has not launched GAMMA or any external clients yet.
    # Always attempt to resume services even if stopping writers fails.
    try:
        ctl.compose(['stop', *WRITERS], timeout=120)
        for service in WRITERS:
            running = ctl.compose(['ps', '-q', '--status', 'running', service],
                                  capture_output=True, text=True, timeout=20).stdout.strip()
            require(not running, 'source writer still running')
        def query(sql):
            return ctl.compose(['exec', '-T', 'postgres', 'psql', '-X', '-qAt',
                                '-v', 'ON_ERROR_STOP=1', '-U', 'aiops', '-d', 'aiops'],
                               input=("SET TIME ZONE 'UTC';\n" + sql).encode(),
                               capture_output=True, timeout=60).stdout

        before = project_snapshot(query)
        backup = ctl.backup()
        archive = Path(backup['archive'])
        require(backup['result'] == 'PASS' and backup['restore_tested'] is False
                and archive.parent == ctl.root / 'backup'
                and re.fullmatch(r'[a-f0-9]{64}', backup['sha256']), 'invalid backup receipt')
        result = restore(ctl, archive.name, backup['sha256'], project_snapshot)
        require(result['result'] == 'PASS' and result['active_database_restored'] is False
                and result['production_authorized'] is False, 'invalid restore receipt')
        require(result['backup_sha256'] == backup['sha256']
                and result['backup_bytes'] == backup['bytes'], 'restore archive identity mismatch')
        after = project_snapshot(query)
        require(before == after, 'source changed during backup or restore')
        require(before == result['snapshot'], 'restored rows or schema differ')
    finally:
        ctl.start()
        ctl.health()
    return {**result, 'source_snapshot_match': 'PASS', 'source_unchanged': True,
            'writers_resumed': True, 'classification': 'POC_ROOTLESS_PG_RESTORE_PROOF',
            'tables': len(before['tables']), 'source_sha': os.environ.get('GITHUB_SHA', 'NOT_ATTESTED')}


def main():
    try:
        require(os.environ.get('GITHUB_ACTIONS') == 'true'
                and os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'
                and os.environ.get('V3_ROOT') == str(CI_ROOT)
                and os.getuid() != 0
                and re.fullmatch(r'[a-f0-9]{40}', os.environ.get('GITHUB_SHA', '')),
                'disposable rootless CI only')
        report = prove(Lifecycle(CI_ROOT))
        print(json.dumps(report, sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print('POC restore qualification failed: ' + type(exc).__name__, file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
