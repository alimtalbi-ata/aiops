#!/usr/bin/env bash
# FS1152: read-only fingerprint of GLPI app-token storage, without printing secrets.
set -euo pipefail
echo "FS1152_MODE=READ_ONLY_GLPI_APP_TOKEN_FORMAT"
echo "FS1152_MUTATION=NONE"
echo "FS1152_PORTAL_MUTATION=NONE"
TOKEN_FILE="$HOME/.config/aiops2/glpi-core/fs1150-app-token"
test -s "$TOKEN_FILE" || { echo "FS1152_ERROR=APP_TOKEN_FILE_MISSING";exit 2; }
python3 - "$TOKEN_FILE" <<'PY'
import json,sys,pathlib,re
v=pathlib.Path(sys.argv[1]).read_text().strip()
print(json.dumps({'type':'local_app_token','length':len(v),'is_hex':bool(re.fullmatch('[a-fA-F0-9]+',v)),'secret_values_exposed':False}))
PY
docker exec -i aiops2-rebuild-glpi-db sh -c 'exec mariadb -uglpi -p"$MARIADB_PASSWORD" glpi --batch --skip-column-names' <<'SQL'
select 'client_token_metadata',id,name,is_active,
       length(app_token),
       case when app_token regexp '^[0-9a-fA-F]+$' then 'HEX' else 'NON_HEX' end,
       case when app_token like '$2y$%' or app_token like '$2a$%' then 'BCRYPT'
            when app_token like '$argon2%' then 'ARGON2'
            else 'OTHER' end
from glpi_apiclients where id in (1,2);
select 'client_acl',id,inet_ntoa(ipv4_range_start),inet_ntoa(ipv4_range_end)
from glpi_apiclients where id in (1,2);
SQL
echo "FS1152_FINAL_STATUS=READ_ONLY_COMPLETE"
