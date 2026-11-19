# QA review — non-disruptive 7770 candidate clone
Reviewed CENTRAL fix 07900989b18f9c6590b5ffb0680a6d138dd379ad; script blob c11899340b0c8f37d8d3b0cc1a7385e296b6e8ca. Static review only; TEAM D did not run it.

## Improvements confirmed
- Existing autonomous source container inspected; no Compose assumptions.
- Candidate must not already exist; source must be running.
- Source image ID, environment, mounts, command, user/workdir and networks are cloned.
- Source container is not stopped; candidate failure removes candidate.
- Inspect snapshot has umask 077 and EXIT cleanup.
- No image build or source mutation is intended.

## BLOCKERS before candidate start
1. `--publish 0.0.0.0:${PORT}:777` binds candidate to every IPv4 interface. This broadens exposure relative to an unknown source binding and is not acceptable by default. Require explicit CENTRAL-approved bind address; default to 127.0.0.1 and verify exact docker port output. Do not infer firewall safety.
2. Candidate reuses all original mounts and environment. Writable bind mounts/volumes and shared external DB/queues can cause duplicate workers, scheduled jobs, or concurrent writes even though source remains running. Inventory process behavior and mount RW modes; require an explicit no-side-effect/standby mode or use read-only mounts where valid before start. Otherwise BLOCKED.
3. Only GET / is checked. Require /health and representative route/API responses, then Playwright journey against candidate. HTTP 200 root alone is insufficient.
4. Secret redaction on `docker logs` is incomplete (only TOKEN/SECRET/PASSWORD/KEY=value single tokens). Avoid emitting candidate logs to shared output; retain privately and redact with approved tooling.
5. Preserve all runtime config not currently cloned: port bindings, extra hosts, DNS, capabilities, security opts, tmpfs, devices, resource limits, logging, labels, healthcheck, sysctls, ulimits, group add, read-only rootfs, shm size, init, IPC/PID modes. Compare source and candidate inspect projections and explicitly document intentional differences.
6. Network attach order and aliases are not preserved; Docker network connect may not reproduce aliases/driver options. Validate exact network config and name resolution.
7. No cleanup/rollback instructions after successful candidate start. Keep candidate clearly isolated; do not switch users until browser acceptance and CENTRAL decision. Provide safe candidate-only cleanup command.

## Verdict
Candidate clone script is materially safer than destructive cutover, but NOT APPROVED to execute as written due wildcard binding and shared writable side-effect risk. Source 7777 must remain running. No runtime execution, no POST, no deployment performed by D.
