#!/usr/bin/env bash
# FS1142: source-IP HTTP probe from existing Portal to GLPI, no auth and no writes.
set -euo pipefail
echo "FS1142_MODE=READ_ONLY_PORTAL_TO_GLPI_NETWORK_PROBE"
echo "FS1142_PRODUCTION_MUTATION=NONE"
echo "FS1142_PORTAL_7777_RESTART=NONE"
echo "FS1142_PORTAL_7777_FILES_CHANGED=NONE"
docker exec -i aiops2-rebuild-portal python - <<'PY'
import json, os, urllib.request, urllib.error
keys=sorted(k for k in os.environ if ('GLPI' in k.upper() or 'ITSM' in k.upper()))
print(json.dumps({'type':'portal_environment_variable_names_only','keys':keys,'secret_values_exposed':False}))
for host in ('aiops2-glpi','aiops2-rebuild-glpi'):
    url=f'http://{host}/apirest.php/initSession'
    req=urllib.request.Request(url,headers={'Accept':'application/json'},method='GET')
    try:
        with urllib.request.urlopen(req,timeout=5) as response:
            status=response.status
            body=response.read(1024)
    except urllib.error.HTTPError as error:
        status=error.code
        body=error.read(1024)
    except Exception as error:
        print(json.dumps({'type':'http_probe','host':host,'transport':'UNREACHABLE','error_type':type(error).__name__}))
        continue
    try:
        parsed=json.loads(body)
        code=parsed[0] if isinstance(parsed,list) and parsed else None
    except (ValueError,TypeError):
        code=None
    print(json.dumps({'type':'http_probe','host':host,'status':status,'glpi_error_code':code,
                      'credentials_sent':False,'method':'GET','mutation':'NONE'}))
PY
echo "FS1142_FINAL_STATUS=READ_ONLY_COMPLETE"
