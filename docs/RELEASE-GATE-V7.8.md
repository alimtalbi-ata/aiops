# AIOps 2.0 — V7.8 Release Gate

V7.8 is the clean-slate runtime qualification baseline. It is not considered operationally qualified until the runtime gates below pass on the target VM.

## Mandatory gates

1. Compose configuration parses.
2. All declared services are created and healthy.
3. PostgreSQL migrations are idempotent.
4. Temporal is reachable only from the internal execution/control networks.
5. Internal application ports 810–819 are not published on the VM.
6. Portal is available on 7777; GLPI 8080; n8n 5678; Prometheus 9090; Grafana 3000.
7. Golden DEMO creates exactly one canonical Run for its idempotency key.
8. Temporal execution is associated with that Run.
9. Stage retries do not create duplicate canonical events or evidence.
10. DEMO/REPLAY/STORY never become production remediation.
11. UNKNOWN/insufficient evidence fails closed.
12. Twin synthetic overrides remain scoped to run_id and never modify the baseline Twin.
13. Outbox delivery uses a lease and an idempotent integration receipt.
14. A legacy retirement action is impossible before the runtime qualification gate is recorded as PASS.

## Evidence rules

A build log is not runtime evidence. A health endpoint is not functional evidence. Synthetic observations are always labelled synthetic. No simulation is presented as a production capture.

## Exit state

- `QUALIFIED`: every mandatory runtime gate passed.
- `QUALIFICATION_FAILED`: one or more mandatory gates failed.
- `STATIC_ONLY`: only source/package checks were performed.
