#!/usr/bin/env bash
# AIOPS2 DEV Docker storage triage: read-only, bounded, no secrets.
# Run as root for metadata visibility. Does NOT start Docker or change files.
set -uo pipefail
export LC_ALL=C
echo "AIOPS2_DOCKER_TRIAGE_V1"
date -u '+collected_at=%Y-%m-%dT%H:%M:%SZ'
echo '== docker service states =='
for unit in docker containerd docker.socket; do
  printf '%s=' "$unit"
  systemctl is-active "$unit" 2>/dev/null || true
done
echo '== daemon configuration (allowlisted fields) =='
python3 - <<'PY'
import json
from pathlib import Path
p=Path('/etc/docker/daemon.json')
try:
    obj=json.loads(p.read_text()) if p.is_file() else {}
    for k in ('data-root','storage-driver'):
        print(f'{k}={obj.get(k, "UNSET")}')
except (OSError,ValueError,TypeError):
    print('daemon_json=UNREADABLE')
PY
echo '== docker root and counts =='
if command -v docker >/dev/null 2>&1; then
  timeout 8 docker info --format 'root={{.DockerRootDir}} containers={{.Containers}} images={{.Images}} driver={{.Driver}}' 2>&1 || true
fi
echo '== known candidate paths =='
for p in /var/lib/docker /var/lib/containerd /home/aiops/aiops-platform/docker-data /home/aiops/aiops-platform /home/aiops/aiops2-auto-deploy; do
  if test -d "$p"; then
    stat -c 'path=%n type=%F owner=%U:%G mode=%a modified=%y' "$p" 2>/dev/null || true
    du -shx "$p" 2>/dev/null || true
  else
    printf 'absent=%s\n' "$p"
  fi
done
echo '== mounts (no environment or credentials) =='
findmnt -T /home/aiops/aiops-platform/docker-data -o TARGET,SOURCE,FSTYPE -n 2>/dev/null || true
findmnt -T /var/lib/docker -o TARGET,SOURCE,FSTYPE -n 2>/dev/null || true
echo '== compose inventory (read-only) =='
timeout 8 docker compose ls -a --format json 2>/dev/null | python3 -c 'import json,sys; s=sys.stdin.read(); a=json.loads(s) if s.strip() else []; print("compose_projects="+str(len(a))); [print("project="+str(x.get("Name","?"))+" status="+str(x.get("Status","?"))) for x in a[:30]]' 2>/dev/null || echo 'compose=UNAVAILABLE'
echo '== deployment checkout (names only) =='
if test -d /home/aiops/aiops2-auto-deploy/repo/.git; then
  git -C /home/aiops/aiops2-auto-deploy/repo status --porcelain=v1 -uno 2>/dev/null | sed -n '1,30p'
fi
echo '== evidence files (presence only) =='
for p in /home/aiops/aiops2-auto-deploy/applied.sha /home/aiops/aiops2-auto-deploy/failed.sha /home/aiops/aiops2-auto-deploy/DEPLOYMENT_BLOCKED /home/aiops/aiops2-auto-deploy/backups/dirty-checkout-20261110T223504Z/local-changes.patch; do
  test ! -e "$p" || stat -c 'present=%n bytes=%s' "$p"
done
echo 'AIOPS2_DOCKER_TRIAGE_DONE'
