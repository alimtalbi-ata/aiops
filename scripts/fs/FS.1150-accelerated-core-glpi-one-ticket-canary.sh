#!/usr/bin/env bash
# FS1150: accelerated canary: dedicated GLPI app client, Core integration network,
# one REAL FS1130 DEMO ticket and durable outbox. Does NOT change Portal.
# Run from repository root. Re-run does not re-POST a confirmed or UNKNOWN row.
set -euo pipefail
umask 077
CORE=aiops2-rebuild-core
PORTAL=aiops2-rebuild-portal
DB=aiops2-rebuild-glpi-db
NET=aiops2-rebuild-integration
WORK=$(mktemp -d /tmp/aiops-fs1150-XXXXXX)
trap 'rm -rf "$WORK"' EXIT
echo "FS1150_MODE=ONE_REAL_CORE_GLPI_CANARY"
echo "FS1150_PORTAL_MUTATION=NONE"
echo "FS1150_MAX_NEW_TICKETS=1"
test -f app/core/glpi_client.py && test -f scripts/fs/fs1136_glpi_outbox.py
# Extract only the user token from the unchanged Portal environment to a protected
# temporary local file; never echo the value or include it in git/logs.
docker exec "$PORTAL" python -c 'import os,sys; x=os.getenv("GLPI_USER_TOKEN",""); sys.stdout.write(x); sys.exit(0 if x else 2)' > "$WORK/user_token"
test -s "$WORK/user_token"
# Attach Core only to integration network. This persists until disconnected/recreated.
if ! docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{println $k}}{{end}}' "$CORE" | grep -Fxq "$NET"; then
  docker network connect "$NET" "$CORE"
  echo "FS1150_CORE_NETWORK_CONNECTED=$NET"
fi
CORE_IP=$(docker inspect -f '{{with index .NetworkSettings.Networks "aiops2-rebuild-integration"}}{{.IPAddress}}{{end}}' "$CORE")
[[ "$CORE_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "FS1150_ERROR=CORE_IP_NOT_FOUND";exit 3; }
echo "FS1150_CORE_INTEGRATION_IP=$CORE_IP"
# Store generated app token locally for reruns. Never overwrite a previously provisioned token.
STATE_DIR="$HOME/.config/aiops2/glpi-core"
mkdir -p "$STATE_DIR";chmod 700 "$STATE_DIR"
TOKEN_FILE="$STATE_DIR/fs1150-app-token"
if [[ ! -s "$TOKEN_FILE" ]]; then openssl rand -hex 32 > "$TOKEN_FILE";chmod 600 "$TOKEN_FILE";fi
APP_TOKEN=$(cat "$TOKEN_FILE")
# SQL literals are only generated from hex digits / verified IPv4.
[[ "$APP_TOKEN" =~ ^[a-f0-9]{64}$ ]]
CLIENT_NAME=aiops2-core-fs1150-dedicated
# Avoid printing the token or database authentication. Preserve existing GLPI client id=1.
docker exec -i "$DB" sh -c 'exec mariadb -uglpi -p"$MARIADB_PASSWORD" glpi --batch --skip-column-names' > "$WORK/sql-result" <<SQL
START TRANSACTION;
INSERT INTO glpi_apiclients
 (entities_id,is_recursive,name,is_active,ipv4_range_start,ipv4_range_end,app_token,dolog_method,date_creation)
SELECT 0,0,'$CLIENT_NAME',1,INET_ATON('$CORE_IP'),INET_ATON('$CORE_IP'),'$APP_TOKEN',0,NOW()
WHERE NOT EXISTS (SELECT 1 FROM glpi_apiclients WHERE name='$CLIENT_NAME');
SELECT 'dedicated_client',id,INET_NTOA(ipv4_range_start),INET_NTOA(ipv4_range_end),
 CASE WHEN app_token='$APP_TOKEN' THEN 'token_match' ELSE 'token_mismatch' END
FROM glpi_apiclients WHERE name='$CLIENT_NAME';
COMMIT;
SQL
cat "$WORK/sql-result"
grep -q 'token_match' "$WORK/sql-result" || { echo "FS1150_ERROR=DEDICATED_CLIENT_TOKEN_MISMATCH";exit 4; }
# Deliver test code only into Core /tmp, not production application source.
docker cp app/core/glpi_client.py "$CORE:/tmp/fs1150_glpi_client.py"
docker cp scripts/fs/fs1136_glpi_outbox.py "$CORE:/tmp/fs1150_outbox.py"
# Pass secrets via stdin rather than Docker command-line environment or log.
# The Python bootstrap imports the exact GitHub client and outbox modules.
{ printf '%s\n' "$APP_TOKEN"; cat "$WORK/user_token"; printf '\n'; } |
docker exec -i "$CORE" python -c '
import os,sys,runpy,importlib.util
app=sys.stdin.readline().strip()
user=sys.stdin.readline().strip()
assert len(app)==64 and user,"missing GLPI credentials"
os.environ["AIOPS_GLPI_URL"]="http://aiops2-rebuild-glpi/apirest.php"
os.environ["AIOPS_GLPI_APP_TOKEN"]=app
os.environ["AIOPS_GLPI_USER_TOKEN"]=user
spec=importlib.util.spec_from_file_location("core.glpi_client","/tmp/fs1150_glpi_client.py")
module=importlib.util.module_from_spec(spec)
sys.modules["core.glpi_client"]=module
spec.loader.exec_module(module)
sys.argv=["/tmp/fs1150_outbox.py","--sync","--limit","1"]
runpy.run_path("/tmp/fs1150_outbox.py",run_name="__main__")
'
echo "FS1150_FINAL_STATUS=CANARY_EXECUTED_REVIEW_TICKET_AND_OUTBOX"
echo "FS1150_ROLLBACK_NOTE=Do not delete a confirmed outbox row or GLPI ticket. To disconnect Core: docker network disconnect $NET $CORE (only after verifying no other dependency). Disable dedicated GLPI API client by name if needed."
