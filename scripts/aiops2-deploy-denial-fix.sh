#!/usr/bin/env bash
set -euo pipefail

REPO="/home/aiops/aiops2-p0-consolidation"
BASE="/home/aiops/aiops-v28-demo/compose.yml"
ACME="/home/aiops/aiops2-acme-rollback-20261029-204439/acme-candidate.override.yml"
WORKER_FIX="/home/aiops/aiops2-acme-rollback-20261029-204439/worker-policy-observe-rollout/candidate.override.yml"

CORE_OLD="sha256:9f50ed6aa55c7f73693aaee7dbc1b632a268446fde43c410b09e1df37f2da546"
WORKER_OLD="sha256:7ae9f6dfaa0e3cecdf4d076eafa49acca2637ebb8c66c6ef7e2f9a9c727ef11b"
WORKER_NEW="sha256:026342546bae36d5aab9ba097ad287fe5e965869f4bcdf1c0a9346fc1d4b5653"

TAG="aiops2-acme-candidate:core-denial-observe-20261029"
DIR="$HOME/aiops2-denial-coordinated-20261029"
mkdir -p "$DIR"

echo "=== PRECONTROLES ==="

test "$(docker inspect --format '{{.Image}}' aiops2-rebuild-core)" = "$CORE_OLD"
test "$(docker inspect --format '{{.Image}}' aiops2-rebuild-worker)" = "$WORKER_OLD"

docker image inspect "$WORKER_NEW" >/dev/null
test -f "$BASE"
test -f "$ACME"
test -f "$WORKER_FIX"

echo "=== CONSTRUCTION CORE ==="

mkdir -p "$DIR/context/core"

for f in \
  critic_denial_prepare.py \
  critic_denial_block.py \
  critic_denial_resume.py
do
  cp "$REPO/app/core/$f" "$DIR/context/core/$f"
done

cat > "$DIR/context/Dockerfile" <<'EOF'
FROM aiops2-acme-core-denial-base:local
COPY core/critic_denial_prepare.py /app/core/critic_denial_prepare.py
COPY core/critic_denial_block.py /app/core/critic_denial_block.py
COPY core/critic_denial_resume.py /app/core/critic_denial_resume.py
RUN python -m py_compile \
    /app/core/critic_denial_prepare.py \
    /app/core/critic_denial_block.py \
    /app/core/critic_denial_resume.py
EOF

docker tag "$CORE_OLD" aiops2-acme-core-denial-base:local

docker build --network none \
  -t "$TAG" \
  "$DIR/context"

echo "=== VALIDATION CORE ==="

docker run --rm --network none --entrypoint python "$TAG" -c '
from core import critic_denial_prepare as p
from core import critic_denial_block as b
from core import critic_denial_resume as r

for module in (p,b,r):
    for mode,command in (
        ("DEMO","OBSERVE"),
        ("REPLAY","OBSERVE"),
        ("STORY","OBSERVE"),
        ("LIVE","EXECUTE"),
    ):
        assert module.valid_denial_command(
            {"mode":mode,"command":command}
        )
    for mode,command in (
        ("DEMO","EXECUTE"),
        ("LIVE","OBSERVE"),
        ("UNKNOWN","EXECUTE"),
    ):
        assert not module.valid_denial_command(
            {"mode":mode,"command":command}
        )
print("CORE CANDIDATE : VALIDATION PASS")
'

echo "=== WORKFLOWS TEMPORAL ==="

docker exec -i aiops2-rebuild-worker python - <<'PY'
import asyncio,os
from temporalio.client import Client

async def main():
    client=await Client.connect(
        os.environ.get("TEMPORAL_ADDRESS","aiops2-temporal:7233"),
        namespace=os.environ.get("TEMPORAL_NAMESPACE","default"),
    )
    count=0
    async for w in client.list_workflows(
        query="ExecutionStatus = 'Running'"
    ):
        count+=1
        print("RUNNING :",w.id)
    print("TOTAL_RUNNING :",count)
    if count:
        raise SystemExit("STOP : workflows en cours")

asyncio.run(main())
PY

echo "=== OVERRIDE COORDONNE ==="

cat > "$DIR/coordinated.override.yml" <<EOF
services:
  aiops2-core:
    image: $TAG
  aiops2-worker:
    image: aiops2-acme-candidate:worker-policy-observe-minimal-20261029
EOF

docker compose -p aiops2-rebuild \
  -f "$BASE" \
  -f "$ACME" \
  -f "$DIR/coordinated.override.yml" \
  config --quiet

echo "=== DEPLOIEMENT CORE + WORKER ==="

docker compose -p aiops2-rebuild \
  -f "$BASE" \
  -f "$ACME" \
  -f "$DIR/coordinated.override.yml" \
  up -d --no-deps --no-build --force-recreate \
  aiops2-core aiops2-worker

echo "=== VERIFICATION DES IMAGES ==="

CORE_NEW="$(docker image inspect --format '{{.Id}}' "$TAG")"
test "$(docker inspect --format '{{.Image}}' aiops2-rebuild-core)" = "$CORE_NEW"
test "$(docker inspect --format '{{.Image}}' aiops2-rebuild-worker)" = "$WORKER_NEW"

echo "=== ATTENTE SERVICES HEALTHY ==="

for service in core worker simulator; do
  name="aiops2-rebuild-$service"
  health="unknown"

  for i in $(seq 1 40); do
    health="$(docker inspect --format '{{.State.Health.Status}}' "$name")"
    if [ "$health" = "healthy" ]; then
      break
    fi
    if [ "$health" = "unhealthy" ]; then
      echo "ECHEC : $name unhealthy"
      exit 1
    fi
    sleep 2
  done

  test "$health" = "healthy" || {
    echo "ECHEC : $name non healthy"
    exit 1
  }

  docker inspect \
    --format '{{.Name}} : {{.State.Status}} / {{.State.Health.Status}} / {{.Image}}' \
    "$name"
done

echo
echo "DEPLOIEMENT COORDONNE TERMINE"
echo "OVERRIDE : $DIR/coordinated.override.yml"
