# Independent QA review — CENTRAL 7770 cutover
Reviewed CENTRAL script commit 01efab9fa74b7e1a747464e1d63eb84be59057ce; current script blob e75f2af274b5b94fcd95ffdaa05578b2a8bce474. Findings only; D did not execute deployment or remote commands.

## Positive safeguards present
- discovers compose project, working dir and config paths from existing container labels
- checks service identity, running state, target port occupancy
- uses exact compose files and project directory
- --no-deps --no-build, only selected portal service
- compares image ID, environment excluding host port, mounts, networks
- health/UI HTTP and published port checks
- rollback trap restores prior host port on post-cutover error
- umask 077 for inspect snapshots

## Blocking acceptance gaps before claiming cutover qualified
1. The script prints PORTAL_URL using hostname -I; avoid printing network address in shared logs. Prefer PORTAL_HOST_PORT=7770 and retrieve address through approved channel.
2. No authenticated/unauthenticated Playwright browser acceptance in the script. HTTP / and /health do not prove the user journey. Run D's unified-7770.spec.cjs plus route checks from approved operator after cutover, before closing 7777 rollback.
3. Add explicit checks for exact old published binding address and protocol, not only host port. Preserve loopback vs wildcard exposure; ensure target bind is identical.
4. Verify resulting published binding exactly equals old host IP + target port + internal 777/tcp; current docker port grep accepts any binding ending :7770.
5. Rollback currently re-applies old host port using same env override. Operator must verify rollback binding and HTTP health after rollback; rollback exit alone is insufficient.
6. Ensure inspect JSON snapshots are retained only in private rootless runtime and securely removed after digest/evidence extraction. They may contain environment secrets despite umask 077.
7. Do not run script until CENTRAL confirms exact container labels/config files and approved operator execution window. No docker compose from any other checkout.

## QA status
Static review: reviewed, not executed. Cutover: NOT RUN by D. Browser acceptance: NOT RUN. No deployment approval issued by TEAM D. Existing portal and rollback port must remain until browser acceptance. No POC or new service.
