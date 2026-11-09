#!/usr/bin/env bash
set -euo pipefail
cd /workspace/aiops
python3 -m venv /workspace/aiops-462-venv
/workspace/aiops-462-venv/bin/python -m pip install --disable-pip-version-check -r app/requirements.txt httpx==0.28.1 pytest==8.4.2
