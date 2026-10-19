# Debian deployment runbook

**Author:** Abdelhalim Talbi

## Build the kit

From a Git checkout on Debian 13:

```bash
bash deploy/package.sh
```

The output is a timestamped ZIP and a SHA-256 sidecar. The kit does not contain a live `.env`, database volumes, production exports or prebuilt images. See [DEBIAN-DEPLOYMENT-KIT.md](DEBIAN-DEPLOYMENT-KIT.md).

## Fresh installation

```bash
bash deploy/install.sh
```

The installer creates a new `.env` with random credentials when none exists, then validates it, builds images, starts the stack and runs health and synthetic E2E qualification. Review and securely back up the generated `.env`; never commit or share it.

Do not copy `config/.env.demo.example` for a shared, staging or production deployment. It contains known demo credentials and is only for an isolated disposable demo.

## Existing installation / upgrade

- An existing `.env` is preserved and never rotated implicitly.
- A known default credential fails preflight unless explicit demo mode is enabled.
- The normal installer does not retire historical services.
- Set `RETIRE_LEGACY=1` only after a verified backup, documented rollback, impact window and explicit approval.
- Never run `docker compose down --volumes` on a persistent host unless data destruction is intended and approved.

## Endpoints

- Portal: `http://<VM>:7777`
- GLPI: `http://<VM>:8080`
- n8n: `http://<VM>:5678`
- Prometheus: `http://<VM>:9090`
- Grafana: `http://<VM>:3000`
- Alertmanager: `http://<VM>:9093`
- Temporal gRPC: internal port 7233 only

## V8 naming and network contract

Runtime containers use the `aiops2-` prefix. Portal external TCP 7777/internal 777; GLPI 8080, n8n 5678, Prometheus 9090, Grafana 3000, Alertmanager 9093. Internal AioOps services use 810–819. Temporal uses 7233 internally.

## Qualification boundary

The static workflow validates source and policy contracts. The isolated runtime workflow builds the images, starts a disposable Compose stack, checks service readiness, and executes the synthetic workflow. Neither result is production qualification or proof that LIVE remediation, DGX, CMDB/RAG or rollback integrations are implemented.
