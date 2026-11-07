#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
echo "FS1136_MODE=ISOLATED_TEST_PLUS_READ_ONLY_EXISTING_INCIDENTS"
echo "FS1136_PRODUCTION_MUTATION=NONE"
docker run --rm -v "$ROOT:/src:ro" -w /src python:3.12-slim sh -ec '
python -m pip install -q "fastapi>=0.110" "pydantic>=2" "requests>=2" "httpx2"
PYTHONPATH=/src/app python /src/scripts/fs/test_fs1136_glpi_integration.py
'
echo "FS1136_EXISTING_CORE_GLPI=READ_ONLY_INSPECTION"
docker exec -i aiops2-rebuild-core python - <<'PY'
import json
from shared.db import db
with db() as c:
    incidents=c.execute("""select count(*),count(*) filter(where synthetic)
        from aiops.incidents where external_id like 'FS1130-%'""").fetchone()
    table=c.execute("select to_regclass('aiops.glpi_ticket_links')").fetchone()[0]
    links=c.execute("""select state,count(*) from aiops.glpi_ticket_links
        group by state""").fetchall() if table else []
print(json.dumps({"type":"glpi_readonly_baseline","fs1130_incidents":incidents[0],
                  "fs1130_synthetic":incidents[1],"ticket_link_table_exists":bool(table),
                  "ticket_link_states":dict(links),"mutation":"NONE"}))
PY
echo "FS1136_FINAL_STATUS=PASS"
