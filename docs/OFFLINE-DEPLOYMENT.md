# AioOps 2.0 R5 — Offline Debian Deployment

The Debian target does not need Git, GitHub, DNS or source-control access. The ZIP is the deployment artifact.

## Required
- Docker Engine
- Docker Compose v2
- required Docker images available locally

## Deployment
```bash
unzip AioOps-2.0-V8.0-R5-FINAL.zip -d /home/aiops/incoming-v8-r5
cd /home/aiops/incoming-v8-r5/aiops2-v8-r5
AIOPS2_PASSWORD='Newaiops26$' AIOPS2_ROOT=/home/aiops/aiops2-v8-r5 bash 00-Deployment/install.sh
bash 00-Deployment/offline-preflight.sh
bash 00-Deployment/start.sh
```

The deployment scripts do not invoke Git. The offline path does not pull images.

## Coexistence
Portal 7777; n8n 15678->5678; GLPI 18080->80; Prometheus 19090->9090; Grafana 13000->3000; Temporal UI 18088->8080; Alertmanager 19093->9093.

Internal calls use Docker service names and internal ports.

Author: Abdelhalim Talbi
