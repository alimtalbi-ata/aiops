# Portal P0 — canonical TCP 7777, OIDC origin and negative authority

**Scope:** Portal app, disposable tests and this Portal-owned document only.
**Status:** SOURCE-ONLY / NO_GO. No host execution, real GLPI write, Core ALLOW,
new stack, second portal, Docker/volume change, deployment or candidate edit.

## Exact contract

- One **desired** DEV browser entry: host TCP **7777**, not 17777.
  `/health` remains an application-liveness 200 and advertises
  `canonical_host_port=7777`, `host_port_binding_verified=false`,
  `runtime_exposure=UNKNOWN`. `AIOPS_PORTAL_HOST_PORT=7777` is
  `CONFIGURED_UNVERIFIED`; 17777/other values are `MISMATCH_UNVERIFIED`.
  No external port is claimed to be reachable from a health response.
- OIDC issuer, authorization and token endpoints remain pinned to portless
  HTTPS origins. The Portal OIDC callback can use
  `https://<portal-host>:7777/auth/oidc/callback`, and the logout
  Origin check must compare the **same explicit port**. 17777, 7778 and
  non-HTTPS callbacks are rejected; no alternate UI port is introduced.
  Existing portless HTTPS callback configuration is accepted only as a
  compatibility configuration, **not** proof of the canonical host entry.
- Identity-only OIDC and shared viewer bearer never establish GLPI human
  User/Profile/Entity/Ticket rights. Run present/foreign/forged projections
  remain identical 503 UNKNOWN. OIDC session status becomes 401 on logout.
  Core/NOC/Copilot/GLPI business GET and positive dispatch stay disabled.
- No host inventory is fetched by the Portal or the CI test. Synthetic
  browser and TestClient requests do **not** prove Debian PortBindings,
  reverse-proxy routing, firewall, TLS termination, DNS or human rights.

## Independent inputs still missing

Before any claim that the single DEV portal is live on 7777, an authorized
read-only operator must supply evidence from the **existing** host reporter or
an approved one-time inventory: container image digest, Compose labels/project,
Docker PortBindings, `ss -lnt`, proxy Host/TLS routes, firewall rules,
HTTP Host/health, network and volume/DB ownership, backup and rollback mapping.
The existing reporter's container count and health alone are insufficient.
Do not infer 7777 from the unrelated 17777 probe.

Before any positive business read, independently attest the IdP issuer,
audience and subject-to-GLPI-user mapping, actual GLPI native Profile/Entity/
Ticket permission for that human, canonical actor+tenant+Run+Incident+ticket
binding, Core response signer rotation/revocation and durable atomic nonce/JTI
ledger. Synthetic GLPI-shaped rows and signed mock ALLOW never qualify these.

## Disposable tests and receipt

```sh
PYTHONPATH=app:tests python -m unittest discover -s tests -p test_portal_single_7777_contract.py -v
PYTHONPATH=app:tests python -m unittest discover -s tests -p test_explore_story_playwright_e2e.py -v
```

The existing Quality browser job imports the focused suite and writes
`portal-single-7777-negative.json` into `AIOPS_E2E_ARTIFACT_DIR`.
Its canonical SHA-256 is computed from the receipt body, with source Git
HEAD, UTC timestamp and `CI_DISPOSABLE_SYNTHETIC_ONLY` provenance. This is
negative test evidence, not a Debian receipt. Require exact-head CI logs,
actual N/N and artifact checksum before reporting PASS.

## In-place migration only after operator evidence and approval

Keep the healthy `aiops2-rebuild-portal` as the candidate for a **reversible
in-place** 7777 entry; do not start a second Portal. Compare the actual
PortBindings, proxy routing and volumes before proposing an explicit Compose
change. Historical rollback container is not the active portal merely because
it exists. The architect owns KEEP/MIGRATE/STOP-LATER/UNKNOWN classification
and any eventual host change; no containers are stopped or deleted by this PR.

**Rollback:** close the source-only Draft or revert its Portal-owned commits
on its own branch. Revert the OIDC origin change and health projection together
if required; preserve sessions, Core/GLPI state and all host volumes. No main
push or candidate merge by the Portal owner.
