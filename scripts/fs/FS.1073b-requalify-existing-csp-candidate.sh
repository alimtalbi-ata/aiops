#!/usr/bin/env bash
set -euo pipefail
echo "FS1073_MODE=NONPROD_CSP_REQUALIFICATION"
docker image inspect aiops2-portal:fs1073-csp-candidate >/dev/null
docker run --rm --network none --entrypoint python aiops2-portal:fs1073-csp-candidate -c '
import ast,pathlib,re,hashlib,base64
s=pathlib.Path("/app/portal/fs1051_visual.py").read_text()
h=pathlib.Path("/app/portal/fs1051_visual.html").read_text()
ast.parse(s)
assert "unsafe-inline" not in s
assert "connect-src" in s
for tag in ("style","script"):
 m=re.search("<"+tag+">(.*?)</"+tag+">",h,re.S)
 assert m,tag
 digest=base64.b64encode(hashlib.sha256(m.group(1).encode()).digest()).decode()
 assert digest in s,tag
print("FS1073_HASHES=PASS")
print("FS1073_NO_UNSAFE_INLINE=PASS")
print("FS1073_STATIC_QUALIFICATION=PASS")
'
echo "FS1073_PRODUCTION_DEPLOY=NOT_PERFORMED"
echo "FS1073_RESULT=PASS"
