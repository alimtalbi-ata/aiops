#!/usr/bin/env bash
set -euo pipefail
echo "FS1069_MODE=EXISTING_PLAYWRIGHT_SNAPSHOT_COMPATIBILITY"
python3 - <<'PY'
import pathlib,subprocess,ast,json
home=pathlib.Path("/home/aiops")
py=home/".local/share/aiops-playwright-venv/bin/python"
script=home/"aiops2-auto-deploy/repo/deploy/debian-portal-playwright-snapshot.py"
receipt=home/".local/state/aiops-debian-agent/portal-playwright/portal-playwright-receipt.json"
assert py.is_file(),"FS1069_PLAYWRIGHT_VENV_PYTHON_MISSING"
p=subprocess.run([str(py),"-c","import playwright.sync_api; print('FS1069_PLAYWRIGHT_IMPORT=PASS')"],capture_output=True,text=True,timeout=15)
print(p.stdout.strip() if p.returncode==0 else "FS1069_PLAYWRIGHT_IMPORT=FAIL",flush=True)
assert p.returncode==0
assert script.is_file(),"FS1069_SNAPSHOT_SCRIPT_MISSING"
source=script.read_text()
tree=ast.parse(source)
print("FS1069_SNAPSHOT_SCRIPT=FOUND",flush=True)
print("FS1069_SCRIPT_FUNCTIONS="+",".join(n.name for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)))[:450],flush=True)
for token in ("argparse","PORTAL","base_url","screenshot","snapshot","chromium","receipt"):
 print("FS1069_FEATURE_"+token.upper()+"="+("YES" if token.lower() in source.lower() else "NO"),flush=True)
if receipt.is_file():
 try:
  data=json.loads(receipt.read_text())
  print("FS1069_RECEIPT=FOUND KEYS="+",".join(sorted(data.keys())[:18]) if isinstance(data,dict) else "FS1069_RECEIPT=FOUND",flush=True)
 except (ValueError,UnicodeError):print("FS1069_RECEIPT=UNREADABLE",flush=True)
else:print("FS1069_RECEIPT=MISSING",flush=True)
print("FS1069_RESULT=PASS",flush=True)
PY
