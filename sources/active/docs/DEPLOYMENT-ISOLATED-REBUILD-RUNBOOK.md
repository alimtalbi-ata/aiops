# AIOps 2.0 — Isolated Reconstruction Deployment Runbook

**Author:** Abdelhalim Talbi  
**Edition:** Core Qualification 2.0.0  
**Scope:** Debian 13, Docker Compose single-host, fresh isolated reconstruction.  
**Policy:** No restore from unverified legacy files; no routine manipulation of production containers; LIVE remediation disabled.

## 1. What this deploys

The cumulative repository/ZIP contains the application sources, Dockerfiles, Compose, environment template, SQL migrations, Temporal bootstrap, deterministic testing provider, fixtures, scripts, qualification tests, schema references, operations guides and SHA-256 manifests.

Core runtime:
- PostgreSQL with canonical run/evidence/decision/learning ledger.
- FastAPI Core, Evidence, Policy, Intelligence (Analyst/Critic), Copilot and Portal.
- Temporal server, dedicated PostgreSQL, Temporal schema/bootstrap jobs, Temporal UI and Worker.
- Simulator and digital-twin service, currently used strictly as a synthetic fixture.
- ITSM GLPI with MariaDB and integration n8n.
- Prometheus, Grafana and Alertmanager.
- Opt-in model-evaluation profile; CI provider in a separate test profile.

The public HTTP entry point is the Portal. Other internal services are not published directly on the host unless the Compose configuration explicitly provides a port.

## 2. Safety and isolation

The default Compose identity `aiops2` is for controlled CI and greenfield development. For an existing Debian host that already contains AIOps and V1/V2 data, **use only** `deploy/install-isolated.sh`.

The isolated installer sets:

| Property | Isolated value |
|---|---|
| Project and container prefix | `aiops2-rebuild` |
| Networks | `aiops2-rebuild-*` |
| Named volumes | `aiops2-rebuild-*` |
| Published address | `127.0.0.1` |
| Portal | `17777` |
| GLPI | `18080` |
| n8n | `15678` |
| Prometheus | `19090` |
| Grafana | `13000` |
| Alertmanager | `19093` |

All ports can be changed through documented `AIOPS_ISOLATED_*_PORT` environment variables. Existing containers, volumes, Compose projects and networks must not be removed or recreated as part of the reconstruction. Container ownership and free-port prechecks must complete before Compose starts.

Secrets are generated locally with OpenSSL into `.env` (mode 0600). Neither `.env`, backups, raw runtime logs nor database data belong in Git or the release ZIP. The published dashboards bind to loopback; expose them remotely through controlled SSH port forwarding or an appropriately secured reverse proxy.

## 3. Windows to Debian, minimal commands

On Windows PowerShell, place the selected cumulative release ZIP in Downloads and transfer it to `/home/aiops`:

```powershell
scp "$HOME\Downloads\AIOps-<VERSION>-Core-Deployment-Kit-<TIMESTAMP>.zip" aiops@<DEBIAN_HOST>:/home/aiops/
ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=10 aiops@<DEBIAN_HOST>
```

On Debian, extract the ZIP into a **new empty directory**, separate from running AIOps stacks:

```bash
mkdir -p /home/aiops/aiops2-rebuild-kit
cd /home/aiops/aiops2-rebuild-kit
unzip /home/aiops/AIOps-<VERSION>-Core-Deployment-Kit-<TIMESTAMP>.zip
bash deploy/install-isolated.sh
```

The installer creates configuration/secrets, selects isolated ports, verifies ownership and conflicts, builds images, starts the Compose services, waits for health, upgrades the schema, and executes built-in qualification and a synthetic demo. It exits nonzero on failure; never treat a partially started stack as qualified.

For preparation **without touching Docker or starting services**:

```bash
bash deploy/install-isolated.sh --configure-only
```

Note: `--configure-only` still creates the local `.env` and generated secrets. It does not start containers.

## 4. Access securely

Forward the Portal from a local Windows terminal:

```powershell
ssh -L 17777:127.0.0.1:17777 aiops@<DEBIAN_HOST>
```

Open `http://127.0.0.1:17777` in the local browser. Similar SSH tunnels can be created for GLPI, Grafana and n8n. Explicit exposure on a remote address requires an approved network/security decision; never assume a bare development service has appropriate public authentication.

## 5. Qualification layers

| Layer | Required proof |
|---|---|
| Syntax/config | Python, Shell, Compose, image definitions and security/preflight checks |
| Database | Fresh migrations, upgrade-from-legacy, immutable triggers, eligibility and approval constraints |
| Build | Application container images plus optional evaluation runner |
| Temporal E2E | A DEMO run proceeds through Analyst, Critic and Policy, persists source evidence and ledger records, completes with zero real effects |
| Model fixture evaluation | Grounding, freshness, severity, injection resistance, contradiction detection and advisory-only proposals |
| Decision ledger | Evaluation dataset hash, provider/model/prompt/policy identifiers, metrics and pass/fail stored as immutable row |
| Release | Runtime and model reports present in `09-Qualification`, archive passes manifest/ZIP verification |
| Real model | NOT QUALIFIED until model endpoint, prompt and dataset-specific tests run |
| LIVE and production | NOT QUALIFIED: require authorized real adapters, HITL, fencing, rollback, verification and dedicated acceptance |

The CI model provider is deterministic and synthetic. A `PASS` is proof of integration correctness **only**, not that a real LLM can diagnose enterprise incidents with production-grade accuracy.

## 6. Built-in commands

From the extracted kit root:

```bash
bash deploy/preflight.sh
bash deploy/wait-stack.sh
bash deploy/migrate.sh
bash tests/qualification.sh
bash tests/synthetic-e2e.sh
bash deploy/qualify-model.sh
```

The last command is opt-in and needs a configured OpenAI-compatible endpoint. It creates a versioned report in `reports/ai-core-evaluation.json`; CI also verifies persistence in PostgreSQL. Missing provider, unsupported schema, invalid evidence references or critic failure must block rather than fabricate results.

Check state with `docker compose --env-file .env ps` and inspect bounded logs with `docker compose --env-file .env logs --tail=100 <service>`. Never post raw `.env`, DB dumps or unsanitized runtime logs to a public issue.

## 7. Backup, failure and rollback discipline

- Always preserve available historical dumps. Do not restore unverified V1/V69 backups into the new V2 canonical database.
- If installation fails, collect `docker compose ... ps`, sanitized logs, migration output and test reports; record the exact source commit and generated ZIP hash.
- Stopping only the isolated deployment: `docker compose --env-file .env down` **without** `-v`. This preserves data volumes.
- Avoid `docker system prune`, `docker compose down -v`, broad wildcard deletions, host reboot or legacy retirement as ordinary troubleshooting.
- The manual retirement script is a separate, explicitly gated future decision; it is never part of isolated installation.
- Database migration rollback is not automatic. Restore to a newly created disposable database first and reconcile schema versions and evidence.

## 8. Next functional phases

After deterministic core and isolated qualification: real inference quality on the target LLM server; full RAG evidence retrieval and CMDB enrichment; policy/HITL and guarded action proposal life cycle; read-only vendor adapters; fault-injection and retry/cancel recovery; followed by a **versioned ACME digital twin** and genuine captured demo/video.

The GitHub branch, Pull Request and `docs/PROJECT-CONTINUITY.md` are the continuity records. Do not rely on an individual ChatGPT conversation window as the sole source of project truth.
