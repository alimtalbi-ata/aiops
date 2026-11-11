# AIOPS2 differential audit — GLPI provenance and read-only boundary (2026-11-11 12:08 Europe/Paris)

Scope: source-level differential acceptance protocol, **not** Debian/E2E evidence. No reconstruction, deployment, ACL relaxation or GLPI mutation.

## Evidence baseline
- main: `app/portal/glpi_operator_view.py` blob `aead2dc83a21db7b8d77bcf79fd99f15c9c1ef98`.
- main: `app/portal/main.py` blob `16d156c912ccc7592383f7d67a6a6a36fef50629`.
- #603 SHA `be8a8c2b5f5ab2b8e95141c106d78197dbef9b40`: Actions run 43001012919 success; does not attest this protocol or runtime.
- Docker rootless inventory is operator-supplied historical evidence only: UID 1001, socket /run/user/1001/docker.sock, 87 containers / 210 images. #557 was a rootful/rootless diagnostic mismatch, not lost storage.

## Before/after differential matrix
| Contract | Current source | v28/V145 / historical rollback | Debian active 7777 / candidate 17778 | Gate |
| --- | --- | --- | --- | --- |
| Dashboard/Core/Twin/Runs | bootstrap denies unqualified tenant ACL (503 UNKNOWN) | NOT_VERIFIED | NOT_VERIFIED | P0 no cross-tenant data |
| NOC | router present, provenance requires independent evidence | NOT_VERIFIED | NOT_VERIFIED | P0 no synthetic LIVE |
| GLPI /itsm | anonymous safe shell, synthetic story explicitly labelled; no ticket data | NOT_VERIFIED | NOT_VERIFIED | P0 no inferred ticket/CI |
| GLPI /api/portal/itsm | viewer authentication does not imply tenant+actor permission | NOT_VERIFIED | NOT_VERIFIED | P0 no GLPI upstream without ACL |
| Copilot | POST gate returns UNKNOWN/503 without qualified tenant | NOT_VERIFIED | NOT_VERIFIED | P0 no upstream question |
| Evidence/Policy/HITL | shell statuses UNKNOWN/NOT_INSTALLED | NOT_VERIFIED | NOT_VERIFIED | P0 no approval or LIVE |
| Navigation/UX | /itsm links to /#integrations; disabled priority filter | NOT_VERIFIED | NOT_VERIFIED | P1 no broken anchors or enabled controls |

## Negative acceptance scenarios — fixtures only
1. **Viewer bearer valid, actor/tenant/GLPI entity absent**: GET /api/portal/itsm must return 503 UNKNOWN / TENANT_ACL_NOT_QUALIFIED, no ticket IDs, no Core/GLPI calls, no cacheable response.
2. **Forged tenant or GLPI entity in request headers/query**: cannot upgrade the shared viewer token into actor authorization. Assert zero upstream calls and no tenant data.
3. **GLPI API 200 but no independently verified mapping ticket↔Run**: /itsm must remain NOT_INSTALLED/UNKNOWN; no fake CONNECTED, no ticket/CI, no LIVE Evidence.
4. **Synthetic ACME story**: browser DOM keeps SYNTHETIC provenance and disabled P1–P4 selector; no action/comment/assign/approve control becomes enabled.
5. **Navigation regression**: /itsm link to /#integrations resolves to exactly one target on the shell; missing/duplicate destination fails UI recipe.
6. **Expired evidence**: source_freshness UNKNOWN/expired cannot be rendered as healthy, LIVE or a valid HITL approval.

## Reproduction / CI gate
Run isolated unit/ASGI tests with fake upstream counters and synthetic tokens only; never use production secrets. Assert 503/no-store/no upstream for (1)(2), and DOM semantics for (3)(4)(5). Record command, test counts, exact SHA and CI run URL. **NOT_EXECUTED in this audit**. PR-specific CI PENDING; previous #603 CI success is not transferable.

## Rollback and handoff
Close Draft PR or revert this sole documentation commit on the isolated branch; no runtime rollback. #555 is the coordination issue. Canonical `docs/ops/HANDOVER-AIOPS2-CURRENT.md` is absent on main and appears owned by Draft #599: do not overwrite concurrently. Coordinator should incorporate this evidence by explicit ownership decision. Debian/E2E NOT_VERIFIED; never infer runtime health from GitHub CI or a rootful Docker query.
