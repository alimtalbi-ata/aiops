# V7.7 Release Gate

Static gate: Bash syntax, Python compilation, SQL audit, service-name audit, port/network contract.

Runtime gate on SRV-DEB-05: Compose start, all health checks, migration, Golden DEMO, event idempotency, evidence idempotency, outbox delivery, Temporal restart/recovery, worker restart/recovery, PostgreSQL restart/recovery, and explicit LIVE fail-closed test.

Do not retire legacy before all runtime gates pass.
