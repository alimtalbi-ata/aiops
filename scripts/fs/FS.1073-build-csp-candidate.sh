#!/usr/bin/env bash
set -euo pipefail
echo "FS1073_MODE=NONPROD_CSP_CANDIDATE_BUILD"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
docker image inspect aiops2-portal:fs1051-visual-candidate >/dev/null
docker build --network=none -f "$ROOT/scripts/fs/Dockerfile.fs1073" -t aiops2-portal:fs1073-csp-candidate "$ROOT"
docker run --rm --network none --entrypoint python aiops2-portal:fs1073-csp-candidate -c '
import ast, pathlib, re, hashlib, base64
p=pathlib.Path("/app/portal/fs1051_visual.py")
s=p.read_text()
h=pathlib.Path("/app/portal/fs1051_visual.html").read_text()
assert "unsafe-inline" not in s
assert "connect-src \\'self\\'" in s
assert "sha256-" in s
ast.parse(s)
for tag in ("style","script"):
 m=re.search("<"+tag+">(.*?)</"+tag+">",h,re.S)
 assert m
 digest=base64.b64encode(hashlib.sha256(m.group(1).encode()).digest()).decode()
 assert digest in s,tag+" CSP hash mismatch"
print("FS1073_HASHES=PASS")
print("FS1073_NO_UNSAFE_INLINE=PASS")
print("FS1073_STATIC_QUALIFICATION=PASS")
'
echo "FS1073_CANDIDATE=aiops2-portal:fs1073-csp-candidate"
echo "FS1073_PRODUCTION_DEPLOY=NOT_PERFORMED"
echo "FS1073_RESULT=PASS"
