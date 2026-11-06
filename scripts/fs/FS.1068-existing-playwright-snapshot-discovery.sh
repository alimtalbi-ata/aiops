#!/usr/bin/env bash
set -euo pipefail
echo "FS1068_MODE=EXISTING_PLAYWRIGHT_SNAPSHOT_DISCOVERY"
echo "FS1068_NO_INSTALL=YES"
python3 - <<'PY'
import os,pathlib,shutil,subprocess
roots=[pathlib.Path("/home/aiops/aiops2-v2-delivery"),pathlib.Path("/home/aiops")]
for cmd in ("node","npm","npx","playwright","chromium"):
 p=shutil.which(cmd)
 print("FS1068_COMMAND_"+cmd.upper()+"="+("AVAILABLE" if p else "MISSING"),flush=True)
for root in roots:
 if not root.exists():continue
 print("FS1068_SCAN_ROOT="+str(root),flush=True)
 matches=[]
 skip={"node_modules",".git",".cache","__pycache__","site-packages",".next","dist","build","logs","data","snapshots","screenshots"}
 count=0
 for base,dirs,files in os.walk(root):
  depth=len(pathlib.Path(base).relative_to(root).parts)
  dirs[:]=[d for d in dirs if d not in skip and (depth<5 or d in (".venv","venv","scripts","tests","tools","qa","e2e"))]
  for filename in files:
   if filename in ("playwright.config.ts","playwright.config.js","playwright.config.mjs","package.json","package-lock.json","pnpm-lock.yaml") or ("playwright" in filename.lower() or "snapshot" in filename.lower() or "screenshot" in filename.lower()):
    p=pathlib.Path(base)/filename
    matches.append(str(p))
    count+=1
    if count>=90:break
  if count>=90:break
 for m in matches[:90]:print("FS1068_FILE="+m,flush=True)
 print("FS1068_MATCH_COUNT="+str(len(matches)),flush=True)
for parent in (pathlib.Path("/home/aiops"),pathlib.Path("/home/aiops/aiops2-v2-delivery")):
 for relative in ("node_modules/.bin/playwright",".venv/bin/playwright","venv/bin/playwright","node_modules/playwright/package.json","node_modules/@playwright/test/package.json"):
  p=parent/relative
  if p.exists():print("FS1068_INSTALL_CANDIDATE="+str(p),flush=True)
print("FS1068_RESULT=COMPLETE",flush=True)
PY
