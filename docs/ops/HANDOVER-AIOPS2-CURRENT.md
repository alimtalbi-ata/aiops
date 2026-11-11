# AIOPS2 — audit differential handover (2026-11-11 10:09 CET)

This file is introduced on an isolated audit branch because the path returned 404 on `main` during this cycle. Coordinate ownership with #555 before integration; do not overwrite any handover maintained on another branch.

## Latest audit

- Differential acceptance protocol: `docs/audit/portal-demo-center-differential-20261111.md`.
- Historical #388 DemoCenter / recorder: head `3c87aa54fac9d370aab42afae8639e6c7d887baa`; loopback CI #41616966592 SUCCESS, not Debian E2E.
- Main bootstrap JS blob `ac58f73c725f5e088081bffed4478ea18585ef5c`: tenant ACL, server-derived actor, stale-response rejection, UNKNOWN/READABLE_UNVERIFIED.
- Active :7777, candidate :17778, v28/V145, rollback images: UNKNOWN. Do not infer runtime regression from source-only comparisons.
- Negative protocol: no-consent recorder, stale permission/stop, navigation route integrity, forged tenant envelope, stale bootstrap, missing NOC/Evidence.
- CI for this audit: NOT_VERIFIED at commit time. Debian: no new host receipt; E2E NOT_VERIFIED.
- #557: operator confirmed Docker rootless (UID 1001, 87 containers, 210 images). Rootful `sudo docker` empty output was a diagnostic mismatch, not data loss. No further storage recovery investigation.
- Rollback: close Draft PR or revert branch-only docs commits. No merge, deployment, runtime, ACL/HITL or stack mutation.
