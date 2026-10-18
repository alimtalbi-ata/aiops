#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
bash deploy/preflight.sh
[ -s images/images.tar ] || { echo 'FAIL|OFFLINE_IMAGE_ARCHIVE_MISSING';exit 1; }
[ -s images/images.sha256 ] || { echo 'FAIL|OFFLINE_IMAGE_CHECKSUM_MISSING';exit 1; }
(cd images && sha256sum -c images.sha256) >/dev/null || { echo 'FAIL|OFFLINE_IMAGE_CHECKSUM';exit 1; }
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
