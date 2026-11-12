# AIOPS2 differential acceptance — DemoCenter / navigation / bootstrap (2026-11-11 10:09 CET)

Scope: GitHub-only source/CI audit. No host changes, no merges, no Docker actions. Do not equate historical PR source, CI loopback, and deployed Debian.

## Provenance and comparison

- Current `main`: `app/portal/portal_bootstrap_client.js` blob `ac58f73c725f5e088081bffed4478ea18585ef5c` (fetched 2026-11-11); read model requires tenant ACL, server-derived actor, `runtime_authenticated=false`, `live_remediation_authorized=false`, and states UNKNOWN or READABLE_UNVERIFIED. UI renders at most 15 Runs from at most 100 accepted items; stale requests are discarded after JSON parse.
- Historical candidate #388 HEAD `3c87aa54fac9d370aab42afae8639e6c7d887baa` documents `/demo-center`, `/assets/demo-center-recorder.js`, consent-gated browser-local capture, links to `/noc`, `/itsm`, Twin impact and story. Historical Chromium loopback CI #41616966592 succeeded (3 source + 6 browser tests), not Debian E2E. No assertion that #388 features exist on main or :7777.
- Historical v28/V145, rollback fs1073/fs1051/fs621, Debian :7777, candidate :17778: behavior UNKNOWN until independently evidenced by timestamped authenticated HTTP and image/source provenance.

| Capability | Current main evidence | Historical #388 evidence | Active/candidate | Differential risk |
|---|---|---|---|---|
| Dashboard/Core/Twin/Runs | Client envelope fail-closed, UNKNOWN/READABLE_UNVERIFIED | not compared | UNKNOWN | P0 tenant/actor disclosure or false LIVE |
| DemoCenter navigation | Not established by inspected client file | Routes + hub described | UNKNOWN | P1 missing entry/destination |
| Consent local recorder | Not established by inspected client file | Consent, cancellation and stale-stop browser tests PASS in loopback CI | UNKNOWN | P0 unwanted capture or stale media reappearance |
| NOC/GLPI/ITSM | Not established by inspected client file | /noc and /itsm links described | UNKNOWN | P1 broken route, false NOC correlation |
| Copilot/Evidence | Not established by inspected client file | not qualified by #388 | UNKNOWN | P0 ACL/HITL or false evidence |
| Navigation keyboard/UX | Not established | browser loopback subset only | UNKNOWN | P1 focus, anchor, route regressions |

## Negative acceptance protocol (isolated fixture; do not use real capture or credentials)

1. With no consent, click Record: assert no `getDisplayMedia` invocation, no blob, no network upload. On permission rejection, assert safe error and no preview.
2. With mocked pending `getDisplayMedia`, revoke consent or clear; resolve delayed permission and stop events: assert no stale blob/preview/download and tracks stopped. A new consent must be explicit.
3. With a synthetic navigation DOM, every historical link actually selected for the candidate must resolve to a unique anchor or a valid same-origin route; 404/405 and duplicate anchors fail. Do not require a historical feature absent from approved candidate scope without product decision.
4. Bootstrap HTTP 200 with `tenant_acl_qualified=false`, or `actor_identity_server_derived=false`, or state LIVE: all dashboard metrics and Runs remain UNKNOWN. No Core/Twin/Copilot upstream requests from unauthorised fixture.
5. Bootstrap A/B overlap then clear: delayed A/B JSON must not overwrite UNKNOWN; `READABLE_UNVERIFIED` must never become LIVE.
6. NOC Grafana HTTP 200 with missing signed/fresh metrics and Evidence missing/expired: status UNKNOWN, never healthy. GLPI writes and Copilot HITL mutations are prohibited without actor/tenant approval.

## Execution / release gates

Run source/static + isolated browser tests at the *exact candidate SHA*, record command, exit status, CI run URL, artifact hash and timestamp. Historical #388 CI success is evidence for #388 only. Compare authorized :7777/:17778 responses with timestamp, authenticated role, image digest and matching source commit. Until then: CI for this audit UNKNOWN; Debian UNKNOWN; E2E NOT_VERIFIED; no demonstrated runtime regression. A 503 due to unqualified tenant ACL is a security-preserving result, not by itself a functional regression.

Rollback: close Draft PR or revert only this documentation commit on isolated branch. Never touch main, stacks, Debian, Docker rootless, cron, secrets, PG/GLPI, ACL/HITL or deploy.

#557: operator-provided rootless UID 1001, socket /run/user/1001/docker.sock, 87 containers / 210 images proves rootful `sudo docker` query was the wrong daemon. This is historical operator evidence, not a fresh host query; do not investigate lost storage or rebuild.
