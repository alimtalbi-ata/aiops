#!/usr/bin/env bash
# FS1144 — inspect GLPI_API_URL shape and resolve it without sending credentials.
set -euo pipefail
echo "FS1144_MODE=READ_ONLY_GLPI_URL_SHAPE_AND_DNS"
echo "FS1144_MUTATION=NONE"
docker exec -i aiops2-rebuild-portal python - <<'PY'
import os,json,urllib.parse,socket
u=os.environ.get('GLPI_API_URL','').strip()
p=urllib.parse.urlsplit(u)
host=p.hostname
print(json.dumps({'type':'url_shape','scheme':p.scheme or None,'host':host,
 'port':p.port if host else None,'path':p.path or None,
 'has_query':bool(p.query),'has_fragment':bool(p.fragment),
 'has_embedded_credentials':bool(p.username or p.password),
 'app_token_present':bool(os.environ.get('GLPI_APP_TOKEN')),
 'user_token_present':bool(os.environ.get('GLPI_USER_TOKEN')),
 'token_values_exposed':False},sort_keys=True))
if host:
 try:
  addrs=sorted({x[4][0] for x in socket.getaddrinfo(host,p.port or (443 if p.scheme=='https' else 80),type=socket.SOCK_STREAM)})
  print(json.dumps({'type':'dns_resolution','host':host,'addresses':addrs},sort_keys=True))
 except Exception as e:
  print(json.dumps({'type':'dns_resolution','host':host,'error_type':type(e).__name__},sort_keys=True))
PY
echo "FS1144_FINAL_STATUS=PASS_READ_ONLY"
