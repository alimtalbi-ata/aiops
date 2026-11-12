#!/usr/bin/env bash
set -Eeuo pipefail

BASE="$HOME/aiops2-operations"
OUT="$BASE/fs373-evidence.json"
TMP="$OUT.tmp"

df_result=$(docker exec aiops2-fs-lab df -P /fs-lab)
du_result=$(docker exec aiops2-fs-lab \
  du -k /fs-lab/aiops2-demo-fill.bin)
ls_result=$(docker exec aiops2-fs-lab \
  ls -ln /fs-lab/aiops2-demo-fill.bin)

export FS373_DF="$df_result"
export FS373_DU="$du_result"
export FS373_LS="$ls_result"

python3 - "$TMP" <<'PY'
import json,os,sys,datetime

df=os.environ["FS373_DF"]
du=os.environ["FS373_DU"]
ls=os.environ["FS373_LS"]

parts=df.splitlines()[-1].split()

assert len(parts)>=6
assert parts[-1]=="/fs-lab"

usage=int(parts[4].rstrip("%"))

data={
    "schema":"aiops2.fs373.evidence.v1",
    "source":"docker-exec:aiops2-fs-lab",
    "collected_at":datetime.datetime.now(
        datetime.timezone.utc
    ).isoformat(),
    "filesystem":"/fs-lab",
    "used_percent":usage,
    "total_kib":int(parts[1]),
    "used_kib":int(parts[2]),
    "available_kib":int(parts[3]),
    "file":"/fs-lab/aiops2-demo-fill.bin",
    "df_raw":df,
    "du_raw":du,
    "ls_raw":ls,
    "remediation_executed":False
}

with open(sys.argv[1],"w") as f:
    json.dump(data,f,ensure_ascii=False,indent=2)

print("EVIDENCE_USAGE=",usage)
PY

mv "$TMP" "$OUT"

docker cp "$OUT" \
  aiops2-rebuild-portal:/tmp/fs373-evidence.json

echo "EVIDENCE_INSTALLED"
