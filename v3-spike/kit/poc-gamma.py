"""Foreground GAMMA launcher for an already seeded dedicated POC kit."""
from contextlib import nullcontext
import hashlib
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys

root=Path(os.environ.get("V3_ROOT","/srv/aiops-v3"))
if not root.is_absolute() or root==Path("/") or root.resolve()!=root:
    raise SystemExit("Dedicated absolute root required")
envfile=root/"poc.env"
if envfile.is_symlink() or envfile.stat().st_uid!=os.getuid() or envfile.stat().st_mode & 0o077:
    raise SystemExit("Unsafe POC env file")
values=dict(line.split("=",1) for line in envfile.read_text().splitlines())
token=values["V3_LAB_TOKEN"]
if not re.fullmatch("[0-9a-f]{64}",token):
    raise SystemExit("Invalid local token")
if os.getuid()==0 or "name=rootless" not in subprocess.check_output(["docker","info","--format","{{json .SecurityOptions}}"],text=True):
    raise SystemExit("Rootless Docker required")
here=Path(__file__).resolve().parent
env=dict(os.environ,V3_ROOT=str(root))
for key in ("V3_DB_PASSWORD","V3_LAB_TOKEN"):
    env.pop(key,None)
project="aiops-v3-poc-"+hashlib.sha256(str(root).encode()).hexdigest()[:12]
compose=["docker","compose","--project-name",project,"--env-file",str(envfile),"-f",str(here/"compose.poc-source.yml")]
def port(service,internal):
    endpoint=subprocess.check_output(compose+["port",service,str(internal)],env=env,text=True).strip()
    match=re.fullmatch(r"127\.0\.0\.1:(\d+)",endpoint)
    if not match or int(match[1]) in (7770,7777,7790):
        raise ValueError("Unverified loopback port")
    return int(match[1])
sys.path.insert(0,str(here.parent/"vertical"))
from http_demo import server
from enterprise_clock import EnterpriseClock
from ai_runtime import read_config
from collector_lab_config import activation, provision_new

mode = sys.argv[1:]
if mode not in ([], ['--provision-collector'], ['--guarded-collector']):
    raise SystemExit('usage: poc-gamma.py [--provision-collector | --guarded-collector]')
if mode:
    from rootless_preflight import source_daemon_preflight
    source_daemon_preflight(root)
    if mode == ['--provision-collector']:
        provision_new(root)
        print('LAB collector provisioned; token in collector-control/collector.token; no server started', flush=True)
        raise SystemExit(0)
    raw_port = os.environ.get('V3_GUARDED_GAMMA_PORT', '')
    if not re.fullmatch(r'[0-9]{4,5}', raw_port) or not 1024 <= int(raw_port) <= 65535:
        raise SystemExit('Explicit stable V3_GUARDED_GAMMA_PORT required')
    gamma_port = int(raw_port)
else:
    if any((root / name).exists() or (root / name).is_symlink()
           for name in ('collector-control', 'collector-authority', 'collector-witness')):
        raise SystemExit('Provisioned collector requires explicit guarded launcher')
    gamma_port = 0
ai_providers=read_config(root)
chatops=None
chatfile=root/'mattermost.env'
if chatfile.exists() or chatfile.is_symlink():
    if chatfile.is_symlink() or chatfile.stat().st_uid!=os.getuid() or chatfile.stat().st_mode & 0o077:
        raise SystemExit('Unsafe Mattermost config')
    chat=dict(line.split('=',1) for line in chatfile.read_text().splitlines())
    if not re.fullmatch(r'[A-Za-z0-9_-]{26,128}',chat['TOKEN']) or not re.fullmatch(r'[a-z0-9]{26}',chat['CHANNEL_ID']):
        raise SystemExit('Invalid Mattermost configuration')
    chatops=(chat['TOKEN'],chat['CHANNEL_ID'])
with (activation(root) if mode else nullcontext(None)) as guard, server(port=gamma_port, collector_guard=guard, core_config=(port("core",810),token,"RUN-CI-CONTEXT"),
            context_config=(port("twin",811),port("evidence",812),"NODE-CI-ROOT","INC-CI-CONTEXT"),
            policy_port=port("policy",813),mattermost_config=chatops,enterprise_clock=EnterpriseClock(root),
            enterprise_collector=runpy.run_path(str(here/'poc-multiasset-observed.py'))['collect'],
            technical_collector=lambda:runpy.run_path(str(here/'poc-technical-observed.py'))['collect'](root),
            ai_providers=ai_providers) as http:
    if guard is not None:
        # Join request threads before releasing the lifetime maintenance lock.
        http.daemon_threads = False
    print(f"POC GAMMA: http://127.0.0.1:{http.server_port}",flush=True)
    http.serve_forever()
