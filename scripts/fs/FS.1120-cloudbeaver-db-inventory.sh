#!/usr/bin/env bash
set -euo pipefail
echo "FS1120_MODE=AUTOMATIC_DATABASE_CREDENTIAL_AND_DRIVER_INVENTORY"
echo "FS1120_SECRETS_OUTPUT=NONE"
echo "FS1120_SQL_MUTATION=NONE"
echo "FS1120_PORTAL_MUTATION=NONE"
python3 - <<'PY'
import json,subprocess,re
names=["aiops2-rebuild-postgres","aiops2-rebuild-temporal-postgres","aiops2-rebuild-glpi-db"]
def inspect(name):
 return json.loads(subprocess.check_output(["docker","inspect",name],text=True))[0]
for name in names:
 c=inspect(name)
 env=dict(item.split("=",1) for item in c["Config"].get("Env",[]) if "=" in item)
 engine="MariaDB" if "glpi" in name else "PostgreSQL"
 # Never print environment values other than nonsecret database/user labels.
 prefix="MARIADB" if engine=="MariaDB" else "POSTGRES"
 dbkeys=[prefix+"_DATABASE",prefix+"_DB"]
 userkeys=[prefix+"_USER"]
 secretkeys=[prefix+"_PASSWORD",prefix+"_ROOT_PASSWORD",prefix+"_PASSWORD_FILE",prefix+"_ROOT_PASSWORD_FILE"]
 db=next((env[k] for k in dbkeys if env.get(k)),None)
 user=next((env[k] for k in userkeys if env.get(k)),None)
 def safe(value):
  return value if value and re.fullmatch(r"[A-Za-z0-9_.-]{1,100}",value) else "UNVERIFIED"
 print("FS1120_DB name=%s engine=%s database=%s user=%s credential_source=%s" % (
  name,engine,safe(db),safe(user),
  "ENV_PRESENT" if any(env.get(k) for k in secretkeys) else "ENV_ABSENT"))
print("FS1120_DB_DISCOVERY=COMPLETE")
PY
echo "FS1120_DRIVER_REGISTRY_CANDIDATES_BEGIN"
docker exec aiops2-rebuild-cloudbeaver sh -c '
find /opt/cloudbeaver -type f \( -iname "*driver*.xml" -o -iname "*driver*.json" -o -name "plugin.xml" \) 2>/dev/null | head -35
' || true
echo "FS1120_DRIVER_REGISTRY_CANDIDATES_END"
echo "FS1120_CLOUDBEAVER_WORKSPACE_CONFIG_BEGIN"
docker exec aiops2-rebuild-cloudbeaver sh -c '
for f in /opt/cloudbeaver/workspace/GlobalConfiguration/.dbeaver/data-sources.json /opt/cloudbeaver/workspace/.data/.cloudbeaver.runtime.conf; do
 [ -f "$f" ] && echo "EXISTS=$f"
done
' || true
echo "FS1120_CLOUDBEAVER_WORKSPACE_CONFIG_END"
echo "FS1120_RESULT=INVENTORY_ONLY"
