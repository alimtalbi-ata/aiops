# AIOPS2 differential acceptance — GLPI status vs operational evidence (2026-11-11 13:12 CET)

Scope: source audit only, no Debian access. Baseline `main:app/portal/glpi_operator_view.py` blob `aead2dc83a21db7b8d77bcf79fd99f15c9c1ef98`; bootstrap client blob `ac58f73c725f5e088081bffed4478ea18585ef5c`. Compare against v28/V145, deployed 7777, candidate 17778, fs1073/fs1051/fs621 only after independent, authorized, timestamped captures. UNKNOWN is not absence.

| Function | Baseline source | Historical / active / candidate | Gate |
|---|---|---|---|
| GLPI /itsm shell | Anonymous HTML with SYNTHETIC and NOT_INSTALLED | UNKNOWN | Never expose real ticket/CI |
| GET /api/portal/itsm | Valid viewer token alone yields 503, UNKNOWN, TENANT_ACL_NOT_QUALIFIED; no upstream | UNKNOWN | P0 fail closed |
| Dashboard/Core/Twin/Runs | Bootstrap JS requires actor_identity_server_derived and tenant_acl_qualified | UNKNOWN | P0 reject forged envelope |
| NOC/Evidence | No runtime attestation from GLPI shell | UNKNOWN | P0 do not infer LIVE |
| Copilot/HITL | Not evidenced by this GLPI source | UNKNOWN | P0 separate auth and mutation gate |
| Navigation | /, /#integrations, /demo/explore-story, /itsm links present in GLPI shell | UNKNOWN | P1 validate destinations |

## Negative acceptance protocol (isolated ASGI fixture, NOT EXECUTED)
1. Mount only the GLPI router with synthetic auth verifier. Spy on all Core, GLPI, ticket, Run, and mutation transports; assert zero calls.
2. Unauthenticated GET `/api/portal/itsm`: expect 401 (or auth verifier's 403), UNAUTHORIZED, security headers and no upstream calls.
3. Authenticated viewer without server-derived tenant+actor ACL: expect exactly HTTP 503, `state=UNKNOWN`, `reason=TENANT_ACL_NOT_QUALIFIED`, `connection_state=NOT_INSTALLED`, `runtime_attested=false`, `glpi_write_enabled=false`; zero upstream calls.
4. Repeat with forged `X-Tenant-ID`, `X-Actor-ID`, `X-Role: admin` and synthetic ticket identifiers: same 503, no leak, no upstream calls.
5. GET `/itsm`: assert labels SYNTHETIC, UNKNOWN, NOT_INSTALLED and no customer ticket/CI; ensure disabled filter and no write action. This is a shell test, not proof of GLPI availability.
6. Negative provenance: even if a separate Grafana/GLPI endpoint returns HTTP 200, no Evidence/Twin/Run is marked LIVE without independently verified tenant ACL, freshness and authoritative mapping.

Record per environment: git SHA, image digest, Docker context/rootless socket provenance, UTC capture time, HTTP status/body digest, auth role (never token), source age, CI run and E2E outcome. Do not confuse source, CI, and host.

## Decision and rollback
Fail if any tenant leakage, upstream read, unauthorized mutation or false LIVE; otherwise mark source gate passed only after executed test. Runtime comparison remains NOT_VERIFIED. #557 is a rootful/rootless diagnostic mismatch per operator evidence (aiops UID1001, /run/user/1001/docker.sock, 87 containers, 210 images); no storage-recovery investigation. Rollback: close Draft PR or revert this one documentation commit on its branch. Never merge, deploy, touch Docker, cron, secrets, PG/GLPI, other stacks or ACL/HITL.
