# V7.2 architecture review

## Critical corrections

1. Legacy retirement is now **after** qualification, never before.
2. Internal services are not published on the host; qualification probes them from inside containers.
3. Integration has a dedicated boundary on TCP 817.
4. DEMO/REPLAY/STORY cannot become LIVE through the simulator.
5. Temporal remains the only workflow executor.
6. PostgreSQL remains business truth; Temporal PostgreSQL is isolated.

## Qualification gate

`docker compose config` → image build → startup → internal health → external health → schema → synthetic E2E → only then optional legacy retirement.

## Remaining production gates

- real Analyst/Critic model adapters;
- durable outbox dispatcher and idempotency receipts for GLPI/n8n;
- SSO/TLS/secrets manager;
- full bi-temporal observation model;
- restart/failure chaos qualification;
- backup/restore qualification of the new stack.
