# AIOPS2 Debian rootless inventory completeness gate (2026-11-12)

Scope: **host observation**, never business readiness. The collector runs only as UID 1001; no installation in this PR.

## Contract
- Docker container output: short ID and state only. Docker image output: image ID only. Repository, tag, names, environment, mounts, labels, logs, volumes and tokens are not persisted.
- Each inventory includes `state`, `count` and `complete` when count and listing succeed. `complete=true` only when count matches returned rows and does not exceed the 150-row cap.
- Inaccessible Docker, command failure, timeout, mismatch or truncation => `UNKNOWN`; never imply a complete inventory from a truncated list. `UNKNOWN` does not imply empty, healthy or safe.
- Host report retains UTC collection time, command-specific errors, 0600 atomic JSON, UID check, flock and 24-file retention from parent #670.
- Existing events/logs/health endpoints remain `UNKNOWN` unless a reviewed allowlist/redaction policy is implemented.
- **Residual risks for reviewer:** systemd unit text and Docker IDs are metadata; validate exposure policy. The count command captures output in memory; consider streaming for exceptionally large hosts. Verify lock-file symlink and output-path safety before cron. Current report exit code 2 is expected because intentionally unconfigured sections remain UNKNOWN.

## Business read model contract (separate service boundary)
Actor and tenant MUST be derived from server authentication; enforce per-object ACL before any read. 401 unauthenticated, 403 unauthorized, no cross-tenant existence leak. Validate run_id/mode/incident_id together; reject missing or contradictory identity. Read envelopes include source/provenance, collected_at, expires_at, pagination cursor, generation and explicit UNKNOWN/ERROR/BLOCKED. Abort and timeout do not become READY; stale generation yields UNKNOWN and null data. No browser-persisted secret or client-provided tenant authority. No GLPI/PG writes, no Policy/HITL changes.

## Negative protocol
`python3 -m unittest discover -s tests/observability -p 'test_debian_rootless_inventory.py' -v`
Test incomplete 210/150 inventory, missing count, unavailable listing, timeout, command error, list cap. Separately qualify UID !=1001, flock contention, unsafe path, rotation and output permissions on an isolated synthetic fixture; test 401/403, cross-tenant, absent/inconsistent IDs, cancellation and stale generation in server integration.

## Coordinator-only installation (NOT EXECUTED)
After code review, security approval and host inspection, deploy reviewed script as aiops UID 1001; use a user crontab entry like:
`*/15 * * * * /usr/bin/flock -n /home/aiops/.local/state/aiops2-observe/.cron.lock /usr/bin/timeout 90s /usr/bin/python3 /home/aiops/aiops2/scripts/observability/debian_rootless_readonly.py >/dev/null 2>&1`
The path is illustrative and must be confirmed; ensure directory owner/mode 0700, runtime UID 1001, output JSON 0600, no existing cron collision, and no external DNS. Capture and monitor exit codes via a separately approved mechanism before enabling. No automatic installation, merge or deployment.

Rollback: close Draft or revert only this branch; no runtime change to undo.
