# Deployment runbook

```bash
cp config/.env.example .env
# review/replace secrets if this is not a disposable demo
./deploy/install.sh
# Legacy retirement is a separate, destructive operation; do not enable it during routine upgrades.
```

The installer does not delete legacy volumes or images. Keep the verified backup until the new platform has passed functional acceptance.

Portal: `http://<VM>:17777` (default; override with `AIOPS_PORTAL_HOST_PORT`)  
GLPI: `http://<VM>:8080`  
n8n: `http://<VM>:5678`  
Prometheus: `http://<VM>:9090`  
Grafana: `http://<VM>:3000`

## V8.0 naming and ports

Runtime containers are prefixed `aiops2-`. Portal external TCP 17777/internal 777 by default (configurable with `AIOPS_PORTAL_HOST_PORT`). GLPI 8080, n8n 5678, Prometheus 9090, Grafana 3000. Internal AioOps services use 810-819. Temporal uses 7233 internally.
