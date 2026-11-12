# AIOPS2 / Portal V3 — handover 2026-11-12 06:10 Europe/Paris

## CODE
F-027 adds executable synthetic negative release gate `tests/observability/test_portal_v3_freshness_f027.py` on isolated Draft branch `audit/portal-v3-freshness-executable-f027-20261112`, stacked on #677. Run `python3 -m unittest tests/observability/test_portal_v3_freshness_f027.py -v` (or `python3 tests/observability/test_portal_v3_freshness_f027.py`) at exact HEAD. Tests cover stale/future/naive timestamps, rootful confusion, inventory mismatch, malformed count, timeout, SHA mismatch and eligible host evidence not equivalent to deploy approval. Test is standalone: it does NOT wire a production release gate. Baseline v28/V145, stable Debian and V3 parity remain UNKNOWN without measured fixtures.

## CI
#677 exact SHA 7a2d3380fafe248e4d94a50779617601409e4d72: GitHub Actions quality gates run 43153809703 completed SUCCESS. This does NOT attest F-027 execution. New branch CI UNKNOWN pending exact HEAD verification. #651 integration guards reportedly standalone, not wired to production controllers; integration qualification required.

## DEBIAN
NOT_INSPECTED. No authenticated SRV-DEB-05 access in this run. Rootless aiops UID 1001 socket /run/user/1001/docker.sock; historic 87 containers / 210 images are NOT fresh evidence. Collector development #670/#673/#676/#679 remains independent; review permissions, redaction, lock and count completeness before host use. #557 is rootful/rootless diagnostic confusion, no storage recovery. No installs, cron, deploy or mutations.

## E2E
NOT_VERIFIED. NO_GO Portal V3: require same-SHA green CI, verified rootless host inventory, baseline parity, backups/rollback and tenant ACL/HITL smoke tests. No LIVE.

## Rollback and coordination
Close F-027 Draft or revert its test/documentation commits; no runtime rollback required. No merge main or change to other stacks. Handoff issue #555.
