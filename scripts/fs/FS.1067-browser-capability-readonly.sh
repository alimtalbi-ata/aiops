#!/usr/bin/env bash
set -euo pipefail
echo "FS1067_MODE=READ_ONLY_BROWSER_CAPABILITY_PROBE"
python3 - <<'PY'
import importlib.util,shutil,subprocess
for name in ("chromium","chromium-browser","google-chrome","google-chrome-stable","firefox"):
 path=shutil.which(name)
 if not path:continue
 p=subprocess.run([path,"--version"],capture_output=True,text=True,timeout=8)
 version=(p.stdout or p.stderr).strip().splitlines()
 print("FS1067_BROWSER="+name+" VERSION="+(version[0][:150] if version else "UNKNOWN"),flush=True)
 if "chrom" in name or "chrome" in name:
  p=subprocess.run([path,"--headless","--no-sandbox","--disable-gpu","--disable-dev-shm-usage","--dump-dom","data:text/html,%3Ctitle%3EFS1067%3C/title%3E"],capture_output=True,text=True,timeout=20)
  ok=p.returncode==0 and "<title>FS1067</title>" in p.stdout
  print("FS1067_HEADLESS_DOM="+("PASS" if ok else "FAIL"),flush=True)
  if not ok:print("FS1067_HEADLESS_EXIT="+str(p.returncode),flush=True)
for module in ("selenium","playwright","websocket","websockets","requests"):
 print("FS1067_PYTHON_"+module.upper()+"="+("AVAILABLE" if importlib.util.find_spec(module) else "MISSING"),flush=True)
print("FS1067_RESULT=COMPLETE",flush=True)
PY
