# Portal P0 — Host 7777 / OIDC cookie downgrade negative contract

**Scope:** Portal Run-route refusal + disposable tests only. **Base:** sole Draft #234 `8b1e121cbd7123d95786133c4cf579030d1bf052`. This source-only PR does **not** re-port #298, modify the integration candidate, deploy a second Portal, or change Core/Worker/ACME/CI workflows/architecture board.

## Security delta

- An **explicit** `__Host-aiops_portal_session` cookie is an attempt to use the server-owned OIDC channel, even if malformed, revoked or expired. The Run API and HTML routes now pass that attempt through `consume_run_acl`; it must return **401** when the handle cannot be resolved. The viewer bearer cannot downgrade a rejected OIDC cookie into an identity.
- Valid OIDC identity is not native GLPI human permission and cannot authorize a Run. Present/foreign/forged Run projections remain the same **503 UNKNOWN** with no upstream Core/GLPI business GET, ticket existence, service bearer or tenant data.
- The **desired** single DEV browser entry is HTTPS Host port **7777**, never 17777. The negative test uses a TestClient Host simulation; this does not prove a Debian listener, firewall, proxy, TLS termination or PortBinding. Run-session now rejects any non-HTTPS Origin before viewer authentication. An Origin of `https://portal.example.test:17777` is rejected against a 7777 Host; a matching 7777 Origin still only returns **503 UNKNOWN**. The existing candidate OIDC callback configuration has not yet integrated source #298's explicit-port handling; do not claim 7777 callback success or mark the port verified.
- `aiops2-rebuild-portal` is **KEEP** based only on the last reporter's healthy container state. No new stack or second UI, no container stop, migration or volume change. The historical rollback container is not an active replacement.

## Required independent authorities (all NOT_ATTESTED)

1. Authorized read-only Debian report with Docker `PortBindings`, `ss -lnt`, Compose project/labels, reverse proxy Host/TLS routes, firewall, DNS, volume/DB ownership, backups and rollback mapping. Probe 17777 is not evidence for 7777.
2. IdP issuer/audience/JWKS and revocation evidence from the real trusted IdP, with an independently governed `issuer + subject + tenant -> GLPI User` binding. Browser headers, shared viewer tokens and fixtures are not authority.
3. Authenticated GLPI-native User/Profile/Entity/Ticket rights (READ versus READMY, entity recursion, actual ownership, timestamp and freshness), plus authoritative Core Run→Incident→ticket/entity binding.
4. Independently attested Core response signing keys, rotation/revocation and durable atomic nonce/JTI replay ledger. Synthetic RSA signatures or in-memory fixtures cannot activate ALLOW.

Until **all** are attested and reviewed, `dispatch_allowed=False`, `core_authz_read_permitted=False`, `RELEASE_STABLE=NO_GO`. No synthetic ALLOW and no real GLPI writes.

## Exact-head reproducibility

```sh
PYTHONPATH=app:tests python -m unittest discover -s tests -p test_portal_host_cookie_negative_contract.py -v
PYTHONPATH=app:tests python -m unittest discover -s tests -p test_explore_story_playwright_e2e.py -v
```

The existing Quality browser entry imports the new three-test suite. With `AIOPS_E2E_ARTIFACT_DIR` set, successful cases emit `portal-host-cookie-*.json`: canonical SHA-256 of the receipt body, Git checkout SHA, UTC time, explicit `CI_DISPOSABLE_SYNTHETIC_ONLY` provenance, and negative status counts. This is not a host attestation. Report N/N, CI exact-head URL and artifact digest **only after** a verified run.

## Rollback / integration handoff

Close this source-only Draft or revert its Portal-owned commits. Keep the existing healthy Portal, Core/GLPI state and all host volumes untouched. Architect alone may selectively integrate reviewed blobs into #234; re-check HEAD, current #294 overlap and #298 source before selection. No main push, merge, deployment, SSH, Docker, GLPI write or LIVE.
