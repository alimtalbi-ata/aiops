# ACME Workbench + Playwright Demo — additive qualification addon

**Architecture decision: ADDON, not a second AIOPS platform.** The platform remains authoritative for Core/Incident/Evidence, Twin, Analyst/Critic, Policy/HITL and GLPI. ACME SAN→Payments is a **synthetic test and demonstration scenario**, not a production incident.

## Existing building blocks (no replacement)

| Plane | Existing component | Purpose |
|---|---|---|
| Workbench / story | ACME SAN P1 → Payments P2, Golden #792 and Convergence #713 | A single operator demonstration scenario |
| Receipt validation | #802/#805 `scripts/acme_receipt_model.py`, `scripts/acme_demo_readiness.py` | Strict 17-stage offline gate, `GO_SIMULATION_ONLY` only |
| Demo UI | `app/portal/demo_v2.py`, existing Portal DemoCenter | Read-only views, no invented evidence |
| Host browser | `deploy/debian-portal-playwright-snapshot.py` (#404/#407) | Existing GET-only, same-origin, private atomic Chromium capture; canonical loopback :7777 |
| NOC offline browser | #735/#780 | Responsive/a11y tests, synthetic render, not host |
| NOC manifest/PNG | #752/#757/#761 | Different 3-viewport manifest formats; no automatic 7-scene equivalence |
| **Addon (this PR)** | `scripts/acme_qualification_addon.py` | Offline aggregation of receipt, existing host metadata, optional 7-scene PNG manifest |

## Three independent qualifications

1. **Fixture gate**: existing Pydantic `assess()` validates the ACME synthetic receipt. `OFFLINE_SIMULATION_GATE_PASS_ONLY` never authorizes LIVE.
2. **Browser evidence metadata**: the addon recognizes the **existing** Debian runner receipt schema and checks checkout SHA, Docker image ID, no live effects and zero error counters. This is metadata consistency, **not proof the host executed**.
3. **Seven-scene evidence bytes**: a distinct `aiops.acme-scene-evidence.v1` manifest enumerates seven named ACME story PNGs, checked by actual SHA256 bytes and basic PNG header. The file is a proposed **adapter contract**, not a Playwright runner. Its declarations (visible SIMULATION, zero external requests, PASS) are **not independently observed** by the addon.

**All runtime axes remain `NOT_VERIFIED`**: exact deployed SHA attestation, Core→Twin correlation, tenant ACL and executed 17-stage sandbox E2E. The addon does not manufacture these results from fixtures, manifests or screenshots.

## CLI (local, read-only)

```bash
python scripts/acme_qualification_addon.py --receipt /path/to/fresh-synthetic-receipt.json
python scripts/acme_qualification_addon.py --receipt /path/to/fresh-synthetic-receipt.json \
  --host-receipt /path/to/portal-playwright-receipt.json \
  --scenes-manifest /path/to/acme-scenes.json --scenes-dir /path/to/private-pngs \
  --expected-sha 0123456789abcdef0123456789abcdef01234567
```

Requires Pydantic v2 via existing #805 dependency. CLI returns 0 only for **offline simulation receipt PASS**, 2 for NO_GO. **A zero exit is not runtime qualification**. The repository's fixed historical positive fixture is stale at real time; unit tests use a frozen clock. Do not alter or backdate real receipts to force a PASS.

Scene IDs: `noc`, `signals`, `twin`, `analyst_critic`, `policy_hitl`, `itsm_worker`, `timeline`. A future read-only browser adapter may produce the manifest **only after confirming actual Portal routes/selectors**. The addon itself performs no HTTP, browser launch, login, Docker operation, host scheduling or external writes.

## Release boundaries

- Keep #806 **closed/unmerged**; no second Playwright engine.
- #807 inventories the existing runners and three incompatible manifest formats; do not treat them as interchangeable.
- Exact-SHA CI, negative tests, route/selector confirmation and separately authorized disposable sandbox browser run before asserting visual demo evidence.
- No merges, Debian deployment, GLPI/Temporal/DB operations or LIVE effects without explicit approval.
- Follow central issue [#804](https://github.com/alimtalbi-ata/aiops/issues/804).
