#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import json,subprocess,sys
s=json.loads(subprocess.check_output(['docker','compose','--env-file','.env','config','--format','json'],text=True))['services']
for name,target,published in [('aiops2-portal',777,7777),('aiops2-n8n',5678,15678),('aiops2-glpi',80,18080),('aiops2-prometheus',9090,19090),('aiops2-grafana',3000,13000),('aiops2-temporal-ui',8080,18088)]:
 if name not in s or not any(int(p.get('target',-1))==target and int(p.get('published',-1))==published for p in s[name].get('ports',[])):sys.exit('FAIL|PORT|'+name)
for child,parent,condition in [('aiops2-temporal-schema','aiops2-temporal-postgres','service_healthy'),('aiops2-temporal','aiops2-temporal-schema','service_completed_successfully'),('aiops2-worker','aiops2-temporal','service_healthy')]:
 if s.get(child,{}).get('depends_on',{}).get(parent,{}).get('condition')!=condition:sys.exit('FAIL|DEPENDENCY|'+child+'|'+parent)
if s['aiops2-temporal'].get('ports'):sys.exit('FAIL|TEMPORAL_EXPOSED')
if s['aiops2-temporal']['image']!='temporalio/server:1.32.1':sys.exit('FAIL|TEMPORAL_IMAGE')
if s['aiops2-temporal-schema']['image']!='temporalio/admin-tools:1.32.1':sys.exit('FAIL|TEMPORAL_ADMINTOOLS')
if not any(v.get('target')=='/etc/temporal/config/dynamicconfig' and v.get('read_only') for v in s['aiops2-temporal'].get('volumes',[])):sys.exit('FAIL|DYNAMICCONFIG_MOUNT')
print('RUNTIME_CONTRACT=PASS')
PY
