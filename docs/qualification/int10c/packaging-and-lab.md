# INT10-C3 — packaging and disposable-lab preparation

## Scope
Preparation only. No container is built, started or connected. No PostgreSQL instance, Temporal server, network listener, database, migration, API/auth route or Worker poller is activated.

## Reuse inventory
- app/worker/int10c_activity_body.py: #348 bounded HTTP authority reader and simulated no-effect body; injected session factory; no Temporal registration.
- app/worker/hitl_reject_core_wire.py: INT09 claim/signal/ACK injected callback; no polling, origin selection, credential acquisition or socket.
- app/worker/hitl_reject_terminal_runtime.py: separate negative terminal recovery helper; injected post; no Temporal signal or ACK.
- app/worker/hitl_reject_notification.py: existing notification validator reused.
- Negative terminal_reject and positive Core resolve remain separate operations. No implicit cross-operation join.

## Disposable-lab design (not executed)
1. A future separately authorized CI job provisions ephemeral PostgreSQL 16 and a local Temporal test server inside the hosted runner only.
2. Unique run-scoped database/schema, task queue, workflow ID, credentials and temporary directory; no host mounts, persistent volumes, shared secrets or external service origins.
3. Seed only synthetic tenant/event/proposal records through test fixtures. Apply no repository migrations in this preparation increment.
4. Execute historical #279 cases in an isolated test process, capture exact Git SHA, image/package digests, PostgreSQL/Temporal versions, JUnit and sanitized logs.
5. Tear down in finally/job cleanup and verify no surviving service/process/artifact contains credentials. Failure to prove teardown means NOT_QUALIFIED.
6. Separate network/HTTP fault injection from in-process callback exceptions; neither implies real production identity or tenant ACL.

## Qualification boundary
The existing INT10C workflow remains offline and must not start services. These static tests prove only that helper modules remain unregistered and dependency-injected. PG16 transaction atomicity, Temporal durable replay, OS-process worker fencing, actual network ACK loss, tenant isolation and teardown remain NOT_TESTED. The historical #279 test module remains .reference, not collected. RT10 NO-GO.
