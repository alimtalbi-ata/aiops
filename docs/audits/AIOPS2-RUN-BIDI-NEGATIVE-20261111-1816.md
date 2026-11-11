# AIOPS2 — differential audit: Run status Unicode spoofing (2026-11-11 18:16 CET)

Scope: portal read-only client, no runtime or stack changes. Source main blob `ac58f73c725f5e088081bffed4478ea18585ef5c` (`app/portal/portal_bootstrap_client.js`). Source inspection only, NOT a deployed finding.

## Differential matrix
| Surface | Current source | v28/V145 / Debian active / candidate | Acceptance |
|---|---|---|---|
| Runs status | `String(run[field] ?? "UNKNOWN").slice(0,256)` into `textContent`; no status enum or Unicode bidi filtering | UNKNOWN | A Run status cannot visually impersonate an attested LIVE state; mark row READABLE_UNVERIFIED |
| Runs list | 100 envelope items accepted, 15 displayed | UNKNOWN | Visible truncation and tenant-scoped retrieval for hidden runs |
| Dashboard/Core/Twin | Envelope requires tenant ACL and server-derived actor | UNKNOWN | Fail closed on invalid envelope |
| NOC/GLPI/Copilot/Evidence | Not evaluated in this slice | UNKNOWN | Independent tenant/HITL/provenance checks |
| Navigation/DemoCenter | Not evaluated | UNKNOWN | Preserve routes and consent |

## Negative acceptance protocol U-018 (NOT EXECUTED)
In a detached browser/DOM fixture with no network access, load the existing JS under a fake `/api/portal/bootstrap` response carrying schema `aiops.portal.readmodels.v1`, provenance `UNATTESTED_UPSTREAM_API_READ`, `tenant_acl_qualified=true`, `actor_identity_server_derived=true`, `runtime_authenticated=false`, `live_remediation_authorized=false`, states dashboard/twin UNKNOWN (null values), runs READABLE_UNVERIFIED. Supply one Run with run_id `R-018`, status `\u202eDEVORPPA\u202c` (Unicode bidi controls), and ordinary mode/scenario/confidence. Inspect the resulting row's rendered text and accessible name.

Expected: status is explicitly UNVERIFIED and bidi controls cannot alter visual order or impersonate operational attestation. No innerHTML; no request to Core/GLPI. The current source only guarantees textContent (HTML injection protection), not bidi-safe display. A failing fixture is a source-level gap, not proof of deployed exploitation.

Companion negatives: forged tenant ACL false -> no rows and UNKNOWN; stale JSON response after clear -> no repopulation; 17 Runs with P0 in position 16 -> truncation visibly disclosed. Preserve authorization and HITL. Do not use real tenant data.

## Evidence, CI and rollback
Evidence: GitHub source blob above; this protocol is **specified, not run**. No v28/V145, image digest, host HTTP, E2E or Debian freshness evidence. CI for this commit must be checked separately; green CI alone cannot attest runtime. Rollback: close Draft PR or revert only this documentation commit on its isolated branch. No merge/deploy/rebuild, no Docker or GLPI changes.

## #557
Operator-confirmed rootless context: aiops UID 1001, socket `/run/user/1001/docker.sock`, 87 containers / 210 images at operator observation. `sudo docker` interrogates different rootful daemon; zero rootful objects is not evidence of missing rootless objects. Observation freshness not revalidated here; no storage recovery.
