# Qualification strategy

### Static
- Python AST compilation.
- No legacy runtime names in application/configuration.
- Compose syntax validation.
- Required service/network/port assertions.

### Runtime
- Every container exists.
- Portal 7777, GLPI 8080, n8n 5678, Prometheus 9090, Grafana 3000 and Alertmanager 9093 respond.
- PostgreSQL is healthy.

### Functional
- Golden DEMO creates an Incident and Run.
- Repeating the same Golden DEMO reuses the same idempotent Run.
- Temporal starts the canonical workflow and the Run reaches RESOLVED within a bounded timeout.
- Every required stage has PASS state and a successful completion event.
- Policy produces a PASS Gate with `SIMULATE` decision in DEMO mode.
- The Portal read model returns the canonical Run detail from Core.
- Twin receives synthetic degradation only for synthetic modes.
- Any BLOCKED/FAILED/CANCELLED terminal state, missing stage, missing gate or timeout fails the test.

### Resilience to add before production
- kill Worker during stage and verify Temporal retry/recovery;
- duplicate execute request;
- stale version command;
- duplicate evidence payload;
- database restart;
- Temporal restart;
- network partition between Core and Policy;
- LIVE attempt to invoke synthetic Twin mutation;
- concurrent Runs on the same service.
