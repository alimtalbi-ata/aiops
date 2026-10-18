# AIOps 2.0 — Clean-Slate Deployment V7.8

ACME Digital Twin + Canonical Run Engine baseline.

## Runtime invariants
- Core owns canonical Run/Incident state.
- Temporal is the only workflow executor.
- Twin owns topology and run-scoped simulation overrides.
- Evidence is append-only and idempotent.
- Policy is fail-closed.
- RAG exposes provenance/context; Intelligence consumes Twin + RAG.
- Portal reads APIs, never databases.
- Demo/Replay/Story are never production mutation modes.
- Integration is isolated from the control plane.

## Ports
External: Portal 7777, GLPI 8080, n8n 5678, Prometheus 9090, Grafana 3000, Alertmanager 9093.
Internal: Core 810, Twin 811, Evidence 812, Policy 813, Copilot 814, Worker 815, Simulator 816, Integration 817, Intelligence 818, RAG 819.
Temporal 7233 is internal only.

## Deployment
```bash
cp config/.env.example .env
chmod 600 .env
./deploy/install.sh
./tests/qualification.sh
./tests/synthetic-e2e.sh
```

Retire legacy only after qualification and backup: `CONFIRM_RETIRE=YES bash deploy/retire-legacy.sh`.

## V7.7
Reliability hardening: outbox lease recovery, deterministic worker identity, serialized run-event sequencing, explicit migration execution, RAG/Intelligence runtime qualification, and clean release packaging.

## Développement cloud

Voir [CLOUD-DEVELOPMENT.md](docs/CLOUD-DEVELOPMENT.md) pour les contrôles locaux et les limites de qualification.
