#!/usr/bin/env bash
# Preflight ONLY: does not apply migration and does not start containers.
set -euo pipefail
export XDG_RUNTIME_DIR=/run/user/1001
export DOCKER_HOST=unix:///run/user/1001/docker.sock
test "$(docker info --format '{{.DockerRootDir}}')" = /home/aiops/.local/share/docker
docker info --format '{{json .SecurityOptions}}' | grep -q '"name=rootless"'
test "$(git branch --show-current)" = feat/worker-v27-denial-reconciliation-20261020
test -f db/migrations/090_critic_denial_outbox.sql
python3 - <<'PY'
from pathlib import Path
for name in ("app/core/main.py", "app/worker/main.py", "app/test_provider/main.py"):
    compile(Path(name).read_bytes(), name, 'exec')
print("V27_PYTHON_SYNTAX=PASS")
PY
python3 - <<'PY'
from pathlib import Path
core=Path('app/core/main.py').read_text()
worker=Path('app/worker/main.py').read_text()
assert "ON CONFLICT (run_id, critique_id) DO NOTHING" in core
assert "r.status='BLOCKED'" in core
assert "durable_denial_intent(rid,mode," in worker
assert "asyncio.create_task(reconcile_denial_loop())" in worker
print("V27_CONTRACT_STATIC=PASS")
PY
echo "V27_READONLY_PREFLIGHT=PASS"
