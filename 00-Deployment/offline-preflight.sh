#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
bash deploy/preflight.sh
if [ -s images/images.tar ];then
  (cd images && sha256sum -c images.sha256) >/dev/null || { echo 'FAIL|OFFLINE_IMAGE_CHECKSUM';exit 1; }
else
  echo 'FAIL|OFFLINE_IMAGE_ARCHIVE_MISSING';exit 1
fi
python3 - <<'PY'
import json,subprocess,sys
s=json.loads(subprocess.check_output(['docker','compose','--env-file','.env','config','--format','json'],text=True))['services']
missing=[]
for image in sorted({v['image'] for v in s.values() if 'image' in v}):
 if subprocess.run(['docker','image','inspect',image],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:missing.append(image)
if missing:sys.exit('FAIL|MISSING_IMAGES|'+','.join(missing))
print('PASS|IMAGES_PRESENT')
PY
echo OFFLINE_PREFLIGHT=PASS
