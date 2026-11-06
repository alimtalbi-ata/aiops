#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.970 | WORKER PATCH PERSISTENCE AUDIT ====='
EXPECTED=ecfd599486aaa32b0f3ea446d192aa9c634635a601b7271b785d2fdaf517dfda
CONTAINER=aiops2-rebuild-worker
SOURCE=/home/aiops/aiops2-patches/fs-portal-v30/build/app/worker/main.py
echo '===== 1. LIVE SOURCE ====='
echo "$EXPECTED  $SOURCE" | sha256sum -c -
docker exec "$CONTAINER" sha256sum /app/worker/main.py
echo '===== 2. CONTAINER IMAGE AND MOUNTS ====='
docker inspect "$CONTAINER" --format 'IMAGE={{.Config.Image}} IMAGE_ID={{.Image}}'
docker inspect "$CONTAINER" --format '{{range .Mounts}}{{if eq .Destination "/app/worker/main.py"}}WORKER_BIND_SOURCE={{.Source}} READ_WRITE={{.RW}}{{end}}{{end}}'
echo '===== 3. COMPOSE CONFIG REFERENCES ====='
for f in /home/aiops/aiops-prometheus-image-patch/compose.metrics-cutover.yml /home/aiops/aiops2-fs-demo-source/integration/worker-fs-candidate/compose.fs-worker.yml /home/aiops/aiops2-patches/fs-portal-v30/build/compose-fs-worker-socket.override.yml /home/aiops/aiops2-patches/fs-portal-v30/build/compose-fs-worker-code.override.yml; do
 if [[ -f "$f" ]]; then
  echo "COMPOSE_FILE=$f"
  grep -nE 'image:|build:|dockerfile:|main.py|worker-fs|worker:' "$f" | head -40 || true
 else echo "MISSING_COMPOSE_FILE=$f"; fi
done
echo '===== 4. SOURCE CANDIDATES ====='
for f in /home/aiops/aiops2-v2-delivery/app/worker/main.py /home/aiops/aiops2-fs-demo-source/app/worker/main.py /home/aiops/aiops2-patches/fs-portal-v30/build/app/worker/main.py; do
 if [[ -f "$f" ]]; then
  printf 'SOURCE_SHA256='; sha256sum "$f"
  if grep -Fq "run not found" "$f" && grep -Fq "run not executable from" "$f"; then echo "GUARDS_PRESENT=YES"; else echo "GUARDS_PRESENT=NO"; fi
 else echo "SOURCE_MISSING=$f"; fi
done
echo '===== SAFETY ====='
echo 'FILES_MODIFIED=NO'
echo 'CONTAINERS_RESTARTED=NO'
echo '===== END FS.970 ====='
