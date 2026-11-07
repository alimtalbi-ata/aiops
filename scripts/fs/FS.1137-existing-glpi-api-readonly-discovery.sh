#!/usr/bin/env bash
# FS1137: read-only discovery of existing GLPI REST configuration. Never prints secret values.
set -euo pipefail
echo "FS1137_MODE=READ_ONLY_EXISTING_GLPI_CONFIGURATION"
echo "FS1137_PRODUCTION_MUTATION=NONE"
docker inspect aiops2-rebuild-glpi --format 'GLPI_CONTAINER_RUNNING={{.State.Running}} GLPI_IMAGE={{.Config.Image}}'
docker inspect aiops2-rebuild-core --format 'CORE_CONTAINER_RUNNING={{.State.Running}}'
echo "FS1137_CORE_ENVIRONMENT_KEYS_ONLY"
docker exec aiops2-rebuild-core python - <<'PY'
import os,json
keys=sorted(k for k in os.environ if any(w in k.upper() for w in ("GLPI","TICKET","INTEGRATION")))
print(json.dumps({"keys":keys,"glpi_url_configured":bool(os.getenv("AIOPS_GLPI_URL")),
 "glpi_app_token_configured":bool(os.getenv("AIOPS_GLPI_APP_TOKEN")),
 "glpi_user_token_configured":bool(os.getenv("AIOPS_GLPI_USER_TOKEN")),
 "mandatory_tickets_enabled":os.getenv("AIOPS_GLPI_TICKETS_REQUIRED","false").lower()=="true"}))
PY
echo "FS1137_GLPI_HTTP_ENDPOINT_PROBE"
docker exec aiops2-rebuild-glpi php -r '
foreach (["/apirest.php","/api.php","/"] as $p) {
  $url="http://127.0.0.1".$p;
  $ch=curl_init($url);
  curl_setopt_array($ch,[CURLOPT_RETURNTRANSFER=>true,CURLOPT_FOLLOWLOCATION=>false,CURLOPT_TIMEOUT=>6]);
  curl_exec($ch);
  $code=curl_getinfo($ch,CURLINFO_HTTP_CODE);
  echo json_encode(["path"=>$p,"http_status"=>$code]).PHP_EOL;
  curl_close($ch);
}' || echo "FS1137_GLPI_HTTP_PROBE_UNAVAILABLE"
echo "FS1137_GLPI_CONFIG_FILE_NAMES_ONLY"
docker exec aiops2-rebuild-glpi sh -c 'find /var/glpi /var/www -maxdepth 4 -type f \( -iname "*api*" -o -iname "*glpi*" \) 2>/dev/null | head -40' || true
echo "FS1137_EXISTING_GLPI_LINKS"
docker exec aiops2-rebuild-core python - <<'PY'
import json
from shared.db import db
with db() as c:
 t=c.execute("select to_regclass('aiops.glpi_ticket_links')").fetchone()[0]
 n=c.execute("select count(*) from aiops.incidents where external_id like 'FS1130-%'").fetchone()[0]
print(json.dumps({"fs1130_incidents":n,"ticket_outbox_exists":bool(t)}))
PY
echo "FS1137_FINAL_STATUS=PASS_READ_ONLY"
