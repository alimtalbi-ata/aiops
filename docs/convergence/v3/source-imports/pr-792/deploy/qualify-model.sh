#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[[ -f .env ]] || { echo "FAIL|missing_env|run_deploy_init_env_first"; exit 2; }
bash deploy/check-secrets.sh .env
mkdir -p reports
docker compose --env-file .env --profile qualification config --quiet
docker compose --env-file .env --profile qualification build aiops2-model-evaluator
AIOPS_EVAL_UID="$(id -u)" AIOPS_EVAL_GID="$(id -g)" docker compose --env-file .env --profile qualification run --rm aiops2-model-evaluator
python3 - <<'PY'
import json, pathlib, sys
p=pathlib.Path("reports/ai-core-evaluation.json")
if not p.is_file():
    print("FAIL|model_evaluation_report_missing")
    raise SystemExit(3)
r=json.loads(p.read_text(encoding="utf-8"))
print("MODEL_EVALUATION="+str(r.get("result"))+"|metrics="+json.dumps(r.get("metrics",{}),sort_keys=True))
raise SystemExit(0 if r.get("result")=="PASS" else 4)
PY
