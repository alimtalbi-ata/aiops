#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[ -s .env ] || { echo 'FAIL|ENV_MISSING';exit 1; }
mkdir -p images
docker compose --env-file .env config --quiet
docker compose --env-file .env build
python3 - <<'PY'
import json,subprocess,sys
d=json.loads(subprocess.check_output(['docker','compose','--env-file','.env','config','--format','json'],text=True))
for name,v in d['services'].items():
 if 'image' not in v:sys.exit('FAIL|SERVICE_IMAGE_TAG_MISSING|'+name)
PY
mapfile -t ALL_IMAGES < <(docker compose --env-file .env config --images | sort -u)
[ "${#ALL_IMAGES[@]}" -gt 0 ] || { echo 'FAIL|NO_IMAGES';exit 1; }
for im in "${ALL_IMAGES[@]}";do
 docker image inspect "$im" >/dev/null || { echo "FAIL|IMAGE_MISSING|$im";exit 1; }
done
docker save -o images/images.tar "${ALL_IMAGES[@]}"
(cd images && sha256sum images.tar > images.sha256)
echo 'IMAGE_EXPORT=PASS'
