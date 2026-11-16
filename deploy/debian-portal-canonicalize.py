#!/usr/bin/env python3
"""Canonicalize ONLY the existing DEV portal Compose service; no other stack edits.

Invoked by the already-authorized Debian poller after SHA-pinned portal delivery.
Backup is private on the host. Never publish Compose/.env contents or Docker logs.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request

DEV = Path('/home/aiops/aiops2-auto-deploy/glpi-ai-ticket-enrichment-e2e')
ENV = Path('/home/aiops/aiops-v28-demo/.env')
STATE = Path('/home/aiops/.local/state/aiops-debian-agent')
ROOT = Path(__file__).resolve().parents[1]
SHA = re.compile(r'[0-9a-f]{40}\Z')


def canonical_text(original, candidate_sha):
    """Minimal text patch, refusing ambiguous/foreign portal blocks."""
    if not SHA.fullmatch(candidate_sha):
        raise ValueError('INVALID_CANDIDATE_SHA')
    lines = original.splitlines(keepends=True)
    anchors = [i for i, line in enumerate(lines) if line.rstrip('\r\n') == '  aiops2-portal:']
    if len(anchors) != 1:
        raise ValueError('PORTAL_BLOCK_AMBIGUOUS')
    start = anchors[0]
    end = next((i for i in range(start + 1, len(lines))
                if lines[i] and not lines[i].startswith((' ', '#', '\n', '\r')) or
                (lines[i].startswith('  ') and not lines[i].startswith('    ') and
                 lines[i].strip().endswith(':'))), len(lines))
    block = lines[start:end]
    if any('\t' in x for x in block):
        raise ValueError('PORTAL_TABS_UNSUPPORTED')
    env_positions = [i for i, x in enumerate(block) if x.rstrip('\r\n') == '    environment:']
    if len(env_positions) != 1:
        raise ValueError('PORTAL_ENV_AMBIGUOUS')
    port_positions = [i for i, x in enumerate(block)
                      if x.startswith('      AIOPS_PORTAL_HOST_PORT:')]
    if len(port_positions) > 1:
        raise ValueError('PORTAL_PORT_DUPLICATED')
    tag = 'aiops2-portal:pinned-' + candidate_sha[:12]
    image_positions = [i for i, x in enumerate(block) if x.startswith('    image:')]
    if len(image_positions) > 1:
        raise ValueError('PORTAL_IMAGE_DUPLICATED')
    if port_positions:
        block[port_positions[0]] = '      AIOPS_PORTAL_HOST_PORT: "7777"\n'
    else:
        block.insert(env_positions[0] + 1, '      AIOPS_PORTAL_HOST_PORT: "7777"\n')
    # The image is checked against the running Docker image ID before this
    # local Compose edit. Existing image tags may be stale; backup preserves it.
    if image_positions:
        block[image_positions[0]] = '    image: "' + tag + '"\n'
    else:
        block.insert(1, '    image: "' + tag + '"\n')
    return ''.join(lines[:start] + block + lines[end:]), tag


def command(args, timeout=30):
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          text=True, timeout=timeout, check=False)
    if proc.returncode:
        raise RuntimeError('COMMAND_FAILED')
    return proc.stdout.strip()


def atomic_write(path, content, mode):
    fd, name = tempfile.mkstemp(prefix='.portal-compose-', dir=str(path.parent))
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def strict_health():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open('http://127.0.0.1:7777/health', timeout=5) as response:
        data = json.loads(response.read(4097))
        return (response.status == 200 and type(data) is dict and
                data.get('status') == 'ok' and
                type(data.get('external_port')) is int and data['external_port'] == 7777)


def main():
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    result = {'schema': 'aiops.debian-portal-compose-canonical.v1',
              'collected_at': None, 'status': 'FAIL', 'reason': 'UNKNOWN',
              'compose_changed': False, 'docker_mutations': 0,
              'rollback_attempted': False, 'rollback_succeeded': None,
              'base_compose_verified': False, 'portal_health_strict': False,
              'candidate_sha': None, 'image_id': None}
    original = None
    path = DEV / 'compose.yml'
    old_image = None
    wrote = False
    recreate_attempted = False
    try:
        manifest = json.loads((ROOT / 'deploy/debian-portal-release.json').read_text())
        pin = manifest['candidate_sha']
        if manifest.get('enabled') is not True or not SHA.fullmatch(pin):
            raise ValueError('RELEASE_NOT_PINNED')
        result['candidate_sha'] = pin
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 131072:
            raise ValueError('COMPOSE_FILE_UNSAFE')
        if not ENV.is_file() or ENV.is_symlink():
            raise ValueError('ENV_FILE_UNSAFE')
        mode = stat.S_IMODE(path.stat().st_mode)
        original = path.read_text(encoding='utf-8')
        patched, tag = canonical_text(original, pin)
        base = ['docker', 'compose', '--project-name', 'aiops2-rebuild',
                '--env-file', str(ENV), '-f', str(path)]
        inspect = lambda fmt: command(['docker', 'inspect', 'aiops2-rebuild-portal',
                                        '--format', fmt])
        if (inspect('{{index .Config.Labels "com.docker.compose.project"}}') != 'aiops2-rebuild' or
            inspect('{{index .Config.Labels "com.docker.compose.service"}}') != 'aiops2-portal' or
            inspect('{{if .State.Health}}{{.State.Health.Status}}{{end}}') != 'healthy' or
            inspect('{{len .Mounts}}') != '0'):
            raise ValueError('PORTAL_OWNERSHIP_HEALTH_OR_MOUNTS')
        old_image = inspect('{{.Image}}')
        old_container = inspect('{{.Id}}')
        if command(['docker', 'image', 'inspect', tag, '--format', '{{.Id}}']) != old_image:
            raise ValueError('PINNED_TAG_NOT_CURRENT_IMAGE')
        result['image_id'] = old_image
        if not strict_health():
            raise ValueError('PORTAL_HEALTH_NOT_STRICT')
        if patched != original:
            backup = STATE / ('portal-compose-backup-' +
                              hashlib.sha256(original.encode()).hexdigest()[:20] + '.yml')
            if not backup.exists():
                atomic_write(backup, original, 0o600)
            atomic_write(path, patched, mode)
            wrote = True
            result['compose_changed'] = True
        # Parse in-memory; never emit resolved environment or config to logs.
        cfg = json.loads(command(base + ['config', '--format', 'json'], timeout=40))
        svc = cfg['services']['aiops2-portal']
        ports = svc.get('ports') or []
        if (svc.get('container_name') != 'aiops2-rebuild-portal' or
            svc.get('image') != tag or svc.get('volumes') or
            str(svc.get('environment', {}).get('AIOPS_PORTAL_HOST_PORT')) != '7777' or
            not any(str(p.get('published')) == '7777' and
                    str(p.get('target')) == '777' and
                    p.get('protocol', 'tcp') == 'tcp' for p in ports)):
            raise ValueError('CANONICAL_COMPOSE_CONTRACT_FAILED')
        result['base_compose_verified'] = True
        if wrote:
            recreate_attempted = True
            command(base + ['up', '-d', '--no-deps', '--no-build', '--force-recreate',
                            'aiops2-portal'], timeout=120)
            for _ in range(40):
                if (inspect('{{.Image}}') == old_image and
                    inspect('{{if .State.Health}}{{.State.Health.Status}}{{end}}') == 'healthy'):
                    try:
                        if strict_health():
                            break
                    except (OSError, ValueError):
                        pass
                time.sleep(3)
            else:
                raise ValueError('POST_RECREATE_HEALTH_FAILED')
            new_container = inspect('{{.Id}}')
            if new_container == old_container or len(new_container) != 64:
                raise ValueError('RECREATE_NOT_ATTESTED')
            result['docker_mutations'] = 1
            result['new_container_id'] = new_container
        result['portal_health_strict'] = strict_health()
        if not result['portal_health_strict'] or inspect('{{.Image}}') != old_image:
            raise ValueError('POST_CHECK_IMAGE_OR_HEALTH')
        result['status'], result['reason'] = 'PASS', ('CANONICALIZED_RECREATED' if wrote else
                                                       'ALREADY_CANONICAL_NOOP')
    except Exception as exc:
        result['reason'] = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        if wrote and original is not None:
            result['rollback_attempted'] = recreate_attempted
            try:
                atomic_write(path, original, mode)
                if not recreate_attempted:
                    result['rollback_succeeded'] = True  # only Compose file was restored
                else:
                    # Restore old image and strict 7777, never touch DB or volumes.
                    with tempfile.TemporaryDirectory(prefix='portal-rollback-', dir=str(STATE)) as td:
                        override = Path(td) / 'rollback.yml'
                        atomic_write(override, 'services:\n  aiops2-portal:\n    image: "' +
                                     old_image + '"\n    environment:\n      AIOPS_PORTAL_HOST_PORT: "7777"\n', 0o600)
                        command(['docker', 'compose', '--project-name', 'aiops2-rebuild',
                                 '--env-file', str(ENV), '-f', str(path), '-f', str(override),
                                 'up', '-d', '--no-deps', '--no-build', '--force-recreate',
                                 'aiops2-portal'], timeout=120)
                    for _ in range(20):
                        try:
                            if (strict_health() and
                                command(['docker', 'inspect', 'aiops2-rebuild-portal',
                                         '--format', '{{.Image}}']) == old_image):
                                result['rollback_succeeded'] = True
                                break
                        except Exception:
                            pass
                        time.sleep(3)
                    if result['rollback_succeeded'] is not True:
                        result['rollback_succeeded'] = False
            except Exception:
                result['rollback_succeeded'] = False
    finally:
        result['collected_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
        atomic_write(STATE / 'portal-compose-result.json',
                     json.dumps(result, sort_keys=True) + '\n', 0o600)
    return 0 if result['status'] == 'PASS' else 78


if __name__ == '__main__':
    sys.exit(main())
