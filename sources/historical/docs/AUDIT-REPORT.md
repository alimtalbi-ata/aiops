# Engineering re-analysis — Big Bang baseline

## Previous weaknesses found

1. Simulator was on a network from which Core was unreachable. Fixed by making Demo creation a Portal/Core responsibility and keeping Simulator isolated.
2. n8n defaulted to SQLite instead of the canonical PostgreSQL service. Fixed by configuring PostgreSQL `n8n` database.
3. GLPI lacked the official auto-install database environment contract. Fixed with `GLPI_DB_HOST/PORT/NAME/USER/PASSWORD` and persistent `/var/glpi` data.
4. Execution was not idempotent at the Core boundary. Fixed with `execution_receipts` and Temporal duplicate-start handling.
5. Business/service/application layers were too small. Expanded Twin seed includes business, service, application, compute, storage, SAN, NAS and network.
6. There was no durable per-stage state. Added `run_stage_state`.
7. No observation/change/incident/impact model existed. Added tables and API foundations.
8. Twin state history lacked a real bi-temporal fact table. Added `twin_facts` with valid time and known time.
9. Grafana had no provisioned data source/dashboard. Added provisioning and a command-center dashboard.
10. Legacy naming could leak into the new runtime. Runtime names are normalized; the retirement script is the only place that intentionally mentions legacy patterns.

## Remaining limitations

The DGX/NIM, RAG, real GLPI ticket bridge and production observability exporters are intentionally represented as contracts/adapters rather than fabricated as working external systems. The Golden Demo is synthetic and explicitly labelled.

Before production, run the resilience scenarios listed in `docs/TEST-STRATEGY.md`, replace demo secrets, pin image digests, and perform a real restore drill.
