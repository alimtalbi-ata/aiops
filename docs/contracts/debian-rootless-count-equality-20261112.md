# Debian ROOTLESS inventory count equality — 2026-11-12

Scope: host telemetry only, never a business health/read-model signal. This draft is stacked on #673 and does not install cron or access Debian.

## Contract delta

A Docker inventory is OBSERVED/complete only when both listing and independent count commands succeed, the listing fits the configured limit, and `count == len(items)`. `count > len(items)` is UNKNOWN/INVENTORY_TRUNCATED; `count < len(items)` is UNKNOWN/INVENTORY_COUNT_MISMATCH. Both remain `complete:false` and cannot be promoted to OK. Counts are sampled at different times: a mismatch can reflect concurrent Docker changes, not necessarily data loss. Treat as UNKNOWN and retry in a subsequent collection; never silently reconcile.

Existing gaps requiring independent review: raw systemd unit output may expose descriptive metadata; lockfile symlink/parent directory hardening; command output limits and image duplicate semantics; endpoints/events/logs intentionally UNKNOWN without safe allowlists. No actor/tenant authentication is implemented by the host collector. Portal reads require independent server-side actor/tenant ACL, 401/403, provenance, freshness, bounded pagination, timeout/cancellation and stale-generation rejection.

## Negative tests

`python3 -m unittest discover -s tests/observability -p 'test_debian_rootless*.py' -v`

Test both mismatch directions, equal count and missing count; additionally review UID 1001, output directory permissions, lock contention, Docker unavailable/timeouts, rotation, JSON and no secrets. Tests here are synthetic and do not qualify Debian/E2E.

## Installation handoff (coordinator only; NOT EXECUTED)

After review, on the approved Debian host under `aiops` UID 1001, verify script SHA, ownership and restricted directory, then perform a one-shot non-production invocation:
`sudo -u aiops env AIOPS_COLLECT_DIR=/home/aiops/.local/state/aiops2-observe /usr/bin/python3 /opt/aiops/scripts/observability/debian_rootless_readonly.py`
Exit 0 = all sections observed, 2 = partial/UNKNOWN, 3 = unsafe user/output directory, 4 = lock busy. Do not install cron until the coordinator approves privacy and permissions. No external DNS, no GLPI/PG/Policy/HITL writes, no Core/Worker/Twin changes.

Rollback: discard draft branch or revert isolated commits; no runtime changes to undo.
