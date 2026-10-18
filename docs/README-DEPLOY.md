# Deployment runbook

```bash
cp config/.env.example .env
# review/replace secrets if this is not a disposable demo
RETIRE_LEGACY=1 ./deploy/install.sh
```

The installer does not delete legacy volumes or images. Keep the verified backup until the new platform has passed functional acceptance.

Portal: `http://<VM>:7777`  
GLPI: `http://<VM>:8080`  
n8n: `http://<VM>:5678`  
Prometheus: `http://<VM>:9090`  
Grafana: `http://<VM>:3000`
