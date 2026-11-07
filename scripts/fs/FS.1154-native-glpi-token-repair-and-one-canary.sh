#!/usr/bin/env bash
# FS1154: native GLPIKey encryption for client #2, auth gate, then one Core outbox ticket.
set -euo pipefail
umask 077
echo "FS1154_MODE=NATIVE_GLPI_TOKEN_REPAIR_AND_ONE_REAL_CANARY"
echo "FS1154_PORTAL_MUTATION=NONE"
echo "FS1154_MAX_NEW_TICKETS=1"
test -f app/core/glpi_client.py && test -f scripts/fs/fs1136_glpi_outbox.py
TOKEN_FILE="$HOME/.config/aiops2/glpi-core/fs1150-app-token"
test -s "$TOKEN_FILE"
WORK=$(mktemp -d /tmp/aiops-fs1154-XXXXXX)
trap 'rm -rf "$WORK"' EXIT
CORE_IP=$(docker inspect -f '{{with index .NetworkSettings.Networks "aiops2-rebuild-integration"}}{{.IPAddress}}{{end}}' aiops2-rebuild-core)
[[ "$CORE_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]
# Encrypt using the GLPI installation itself. The plaintext is stdin only.
docker exec -i aiops2-rebuild-glpi php -r '
require "/var/www/glpi/inc/includes.php";
require_once "/var/www/glpi/src/GLPIKey.php";
$v=trim(stream_get_contents(STDIN));
if (!preg_match("/^[0-9a-f]{64}$/D",$v)) {fwrite(STDERR,"FS1154_INVALID_APP_TOKEN\n");exit(2);}
$key=new GLPIKey();
$cipher=$key->encrypt($v);
if ($key->decrypt($cipher)!==$v) {fwrite(STDERR,"FS1154_GLPIKEY_ROUNDTRIP_FAILED\n");exit(3);}
echo $cipher;
' < "$TOKEN_FILE" > "$WORK/cipher"
# GLPIKey ciphertext must be a safe SQL literal; never print it.
python3 - "$WORK/cipher" <<'PY'
import pathlib,sys,re
s=pathlib.Path(sys.argv[1]).read_text()
if not (80<=len(s)<=1024 and re.fullmatch(r'[A-Za-z0-9+/=_-]+',s)):
 print("FS1154_ERROR=UNEXPECTED_GLPIKEY_CIPHERTEXT_FORMAT");sys.exit(3)
print("FS1154_GLPIKEY_ENCRYPTION=READY")
PY
CIPHER=$(cat "$WORK/cipher")
# Fail closed unless the row is exactly the FS1150 dedicated client and matches Core IP.
docker exec -i aiops2-rebuild-glpi-db sh -c 'exec mariadb -uglpi -p"$MARIADB_PASSWORD" glpi --batch --skip-column-names' > "$WORK/sql" <<SQL
START TRANSACTION;
UPDATE glpi_apiclients SET app_token='$CIPHER',app_token_date=NOW()
 WHERE id=2 AND name='aiops2-core-fs1150-dedicated' AND is_active=1
 AND ipv4_range_start=INET_ATON('$CORE_IP') AND ipv4_range_end=INET_ATON('$CORE_IP');
SELECT 'updated_rows',ROW_COUNT();
COMMIT;
SQL
grep -Fxq $'updated_rows\t1' "$WORK/sql" || { echo "FS1154_ERROR=DEDICATED_CLIENT_NOT_UPDATED";exit 4; }
echo "FS1154_DEDICATED_CLIENT_2=ENCRYPTED"
# Authenticate from Core before any ticket creation. No secret in output.
{ cat "$TOKEN_FILE"; docker exec aiops2-rebuild-portal python -c 'import os,sys;sys.stdout.write(os.environ["GLPI_USER_TOKEN"]+"\n")'; } |
docker exec -i aiops2-rebuild-core python -c '
import sys,json,urllib.request,urllib.error
app=sys.stdin.readline().strip();user=sys.stdin.readline().strip()
if not (app and user):sys.exit("FS1154_MISSING_CREDENTIAL")
base="http://aiops2-rebuild-glpi/apirest.php"
try:
 req=urllib.request.Request(base+"/initSession",headers={"App-Token":app,"Authorization":"user_token "+user})
 with urllib.request.urlopen(req,timeout=15) as r:
  token=json.loads(r.read(8192)).get("session_token")
  assert token
  print(json.dumps({"type":"auth","http_status":r.status,"session_established":True}))
 req=urllib.request.Request(base+"/killSession",headers={"App-Token":app,"Session-Token":token})
 with urllib.request.urlopen(req,timeout=15) as r:print(json.dumps({"type":"session_close","http_status":r.status}))
except urllib.error.HTTPError as e:
 print(json.dumps({"type":"auth","http_status":e.code,"result":"FAILED_NO_POST"}));sys.exit(5)
'
# The existing outbox implementation opens GLPI session BEFORE any DB mutation.
docker cp app/core/glpi_client.py aiops2-rebuild-core:/tmp/fs1150_glpi_client.py >/dev/null
docker cp scripts/fs/fs1136_glpi_outbox.py aiops2-rebuild-core:/tmp/fs1150_outbox.py >/dev/null
{ cat "$TOKEN_FILE"; docker exec aiops2-rebuild-portal python -c 'import os,sys;sys.stdout.write(os.environ["GLPI_USER_TOKEN"]+"\n")'; } |
docker exec -i aiops2-rebuild-core python -c '
import os,sys,runpy,importlib.util
app=sys.stdin.readline().strip();user=sys.stdin.readline().strip()
if not (app and user):sys.exit("FS1154_MISSING_CREDENTIAL")
os.environ.update(AIOPS_GLPI_URL="http://aiops2-rebuild-glpi/apirest.php",AIOPS_GLPI_APP_TOKEN=app,AIOPS_GLPI_USER_TOKEN=user)
spec=importlib.util.spec_from_file_location("core.glpi_client","/tmp/fs1150_glpi_client.py")
module=importlib.util.module_from_spec(spec);sys.modules["core.glpi_client"]=module;spec.loader.exec_module(module)
sys.argv=["/tmp/fs1150_outbox.py","--sync","--limit","1"]
runpy.run_path("/tmp/fs1150_outbox.py",run_name="__main__")
'
echo "FS1154_FINAL_STATUS=CANARY_EXECUTED_REVIEW_OUTBOX"
