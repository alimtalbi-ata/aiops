#!/usr/bin/env bash
# Configure the existing AIOps2 stack for the operator-supplied NGX/NIM endpoint.
# Application containers only. No Debian host administration, DB migration, or GLPI write.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
NIM_BASE_URL="http://10.79.94.31:8000/v1"
TIMEOUT="${NIM_TIMEOUT_SECONDS:-105}"
RUN_DEMO=0
if [[ "${1:-}" == "--run-acme-demo" ]]; then RUN_DEMO=1
elif [[ $# -gt 0 ]]; then echo "Usage: $0 [--run-acme-demo]" >&2; exit 2
fi

[[ "$(id -u)" -ne 0 ]] || { echo "BLOCKED|run_as_aiops_not_root"; exit 2; }
[[ -f .env ]] || { echo "BLOCKED|missing_existing_dotenv_run_deploy_init_env_first"; exit 2; }
[[ -f compose.yml && -f scripts/qualify_nim_runtime.py ]] || { echo "BLOCKED|incomplete_checkout"; exit 2; }
command -v docker >/dev/null
command -v python3 >/dev/null
docker compose version >/dev/null
docker info >/dev/null
chmod 600 .env
umask 077
BACKUP=""
rollback_config_on_error() {
  local status=$?
  if [[ $status -ne 0 && -n "$BACKUP" && -f "$BACKUP" ]]; then
    cp -p "$BACKUP" .env
    chmod 600 .env
    docker compose --env-file .env up -d \
      aiops2-intelligence aiops2-worker aiops2-copilot aiops2-portal >/dev/null 2>&1 || true
    echo "CONFIG_ROLLBACK=ATTEMPTED"
    echo "ENV_BACKUP=$BACKUP"
  fi
  exit "$status"
}
trap rollback_config_on_error ERR

# Probe from Debian host, without credentials, and select the exact served model ID.
MODEL_ID="$(NIM_BASE_URL="$NIM_BASE_URL" python3 - <<'PY'
import json, os, sys, urllib.request
url=os.environ["NIM_BASE_URL"].rstrip("/")+"/models"
req=urllib.request.Request(url, headers={"Accept":"application/json"}, method="GET")
try:
    with urllib.request.urlopen(req, timeout=10) as response:
        data=json.loads(response.read(1_000_000).decode("utf-8"))
except Exception as exc:
    print("NGX_MODELS_UNAVAILABLE:"+type(exc).__name__, file=sys.stderr)
    raise SystemExit(2)
rows=data.get("data",[]) if isinstance(data,dict) else []
ids=[x["id"] for x in rows if isinstance(x,dict) and isinstance(x.get("id"),str) and x["id"]]
matches=[x for x in ids if "nemotron" in x.lower() and ("120b" in x.lower() or "120-b" in x.lower())]
if len(matches)==1: selected=matches[0]
elif len(ids)==1: selected=ids[0]
else:
    print("MODEL_SELECTION_REQUIRED available_ids="+json.dumps(ids),file=sys.stderr)
    raise SystemExit(3)
print(selected)
PY
)" || { echo "BLOCKED|NGX_model_discovery_failed"; exit 2; }
[[ -n "$MODEL_ID" ]] || { echo "BLOCKED|empty_model_id"; exit 2; }
printf 'NGX_ENDPOINT=%s\nNGX_MODEL=%s\n' "$NIM_BASE_URL" "$MODEL_ID"

# Run a real unauthenticated completion before touching the running stack.
python3 scripts/qualify_nim_runtime.py \
  --base-url "$NIM_BASE_URL" \
  --model "$MODEL_ID" \
  --timeout "$TIMEOUT" \
  --report artifacts/nim-runtime-qualification.json

# Keep a protected recovery copy of the existing environment.
BACKUP=".env.backup-nim-$(date -u +%Y%m%dT%H%M%SZ)"
cp -p .env "$BACKUP"
chmod 600 "$BACKUP"
export NIM_BASE_URL MODEL_ID NIM_TIMEOUT_SECONDS="$TIMEOUT"
python3 - <<'PY'
import os, pathlib, tempfile
path=pathlib.Path(".env")
lines=path.read_text(encoding="utf-8").splitlines()
keys={
    "LLM_PROVIDER_NAME":"NVIDIA_NIM",
    "LLM_BASE_URL":os.environ["NIM_BASE_URL"],
    "LLM_MODEL":os.environ["MODEL_ID"],
    "LLM_API_KEY":"",
    "AIOPS_DEMO_PROVIDER_KIND":"REAL",
    "LLM_TIMEOUT_SECONDS":os.getenv("NIM_TIMEOUT_SECONDS","120"),
}
for key in keys:
    if sum(line.startswith(key+"=") for line in lines)>1:
        raise SystemExit("BLOCKED|duplicate_env_key|"+key)
seen=set()
out=[]
for line in lines:
    key=line.split("=",1)[0] if "=" in line else ""
    if key in keys:
        out.append(key+"="+keys[key]); seen.add(key)
    else:
        out.append(line)
for key,value in keys.items():
    if key not in seen: out.append(key+"="+value)
fd,tmp=tempfile.mkstemp(prefix=".env.nim.",dir=".")
try:
    with os.fdopen(fd,"w",encoding="utf-8") as stream:
        stream.write("\n".join(out)+"\n")
    os.chmod(tmp,0o600)
    os.replace(tmp,path)
finally:
    if os.path.exists(tmp): os.unlink(tmp)
print("ENV_UPDATED=LLM_PROVIDER_NAME,LLM_BASE_URL,LLM_MODEL,LLM_API_KEY,AIOPS_DEMO_PROVIDER_KIND,LLM_TIMEOUT_SECONDS")
PY

docker compose --env-file .env config --quiet
docker compose --env-file .env up -d --build \
  aiops2-intelligence aiops2-worker aiops2-copilot aiops2-portal

# Verify the exact endpoint from inside the Intelligence container, then check service readiness.
docker compose --env-file .env exec -T aiops2-intelligence python - <<'PY'
import json, os, time, urllib.request
base=os.environ["LLM_BASE_URL"].rstrip("/")
model=os.environ["LLM_MODEL"]
def get(path):
    req=urllib.request.Request(base+path,headers={"Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=12) as r: return json.loads(r.read(1_000_000))
models=get("/models")
ids=[x.get("id") for x in models.get("data",[]) if isinstance(x,dict)]
if model not in ids: raise SystemExit("BLOCKED|container_cannot_see_configured_NIM_model")
payload={"model":model,"messages":[
 {"role":"system","content":"You are a connectivity probe."},
 {"role":"user","content":"Reply exactly AIOPS2_CONTAINER_NIM_OK"}
],"temperature":0,"max_tokens":32}
req=urllib.request.Request(base+"/chat/completions",data=json.dumps(payload).encode(),
 headers={"Content-Type":"application/json","Accept":"application/json"},method="POST")
started=time.monotonic()
with urllib.request.urlopen(req,timeout=120) as r: result=json.loads(r.read(1_000_000))
choices=result.get("choices",[])
answer=choices[0].get("message",{}).get("content","").strip() if choices else ""
if answer!="AIOPS2_CONTAINER_NIM_OK":
 raise SystemExit("BLOCKED|container_NIM_completion_marker_mismatch")
usage=result.get("usage") if isinstance(result.get("usage"),dict) else {}
print(json.dumps({"container_nim":"PASS","model":model,
 "latency_ms":round((time.monotonic()-started)*1000,2),
 "prompt_tokens":usage.get("prompt_tokens"),
 "completion_tokens":usage.get("completion_tokens"),
 "total_tokens":usage.get("total_tokens"),
 "api_key_used":False},sort_keys=True))
PY

docker compose --env-file .env exec -T aiops2-intelligence python - <<'PY'
import json, urllib.request
with urllib.request.urlopen("http://127.0.0.1:817/ready",timeout=5) as r: ready=json.load(r)
if ready.get("provider")!="NVIDIA_NIM" or ready.get("provider_configured") is not True:
 raise SystemExit("BLOCKED|intelligence_not_ready_for_NVIDIA_NIM")
print(json.dumps({"intelligence_ready":ready.get("status"),
 "provider":ready.get("provider"),"model":ready.get("model"),
 "internal_auth_configured":ready.get("internal_auth_configured")},sort_keys=True))
PY

docker compose --env-file .env ps
echo "NIM_RUNTIME_CONFIGURATION=PASS"
echo "ENV_BACKUP=$BACKUP"
echo "DATABASE_MIGRATIONS=NOT_RUN"
echo "GLPI_WRITES=NOT_RUN"
echo "LIVE_REMEDIATION=DISABLED"
trap - ERR

if [[ "$RUN_DEMO" -eq 1 ]]; then
  docker compose --env-file .env --profile demo build aiops2-demo-runner
  docker compose --env-file .env --profile demo run --rm aiops2-demo-runner --confirm-synthetic-demo
fi
