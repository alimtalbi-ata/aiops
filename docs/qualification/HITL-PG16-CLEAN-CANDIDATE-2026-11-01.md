# P0 HITL — candidate PG16 outbox SQL/DR qualification (2026-11-01)

**Status:** Draft, isolated DEV-only test port; RELEASE_STABLE=NO_GO. Architect is the only integrator.

## Provenance and ownership

- Sole integration candidate: [#234](https://github.com/alimtalbi-ata/aiops/pull/234), branch `integration/enterprise-slice-main-20261031-2230`, observed base `0e6ee415b5daddb343a98e0a5672efd42de4bd74`; main `ae7c3e5102b99a66bd7806d602146f1309a9749d`.
- Historical source: [#204](https://github.com/alimtalbi-ata/aiops/pull/204) `5285aec4359a8132cb6c5801dc8d3a18118930fc`, stacked on [#194](https://github.com/alimtalbi-ata/aiops/pull/194) `40d38705cf2bde3be6052340442c117a81908f65`. Source [Quality 41241099554](https://github.com/alimtalbi-ata/aiops/actions/runs/41241099554) 6/6 and PG16 14/14, DR and Worker/Temporal restart were **SOURCE_ONLY**; no status inheritance.
- Architect already integrated #239 Policy no-effect on #234. Do **not** re-port it. Public Policy HTTP remains exactly `state`, `decision`, `reason`.
- Candidate's installed ordered migrations `001,004,009,010,011,012` were independently qualified in disposable PG16 by [Quality 41253781380](https://github.com/alimtalbi-ata/aiops/actions/runs/41253781380), 3/3 jobs; installed-chain 3/3. Exact candidate HEAD and workflow status must be rechecked before integration.
- Source Git blob pins: 009 `bfed91982654b6baf0026408fa5134a22af421bb`; 010 `1ddafd94639af60ce38b6df0acafd7f63d6b4af2`; 011 `b096af57cb19b9618e3d7d4d68a8ef3d56890934`; 012 `9408dcf9d92d5bfbdb75968a5a0b0a55f2985457`. No migration copied or edited.

## Focused delta

- `tests/test_hitl_pg16_candidate_outbox.py`: five independent real PostgreSQL 16 SQL-model tests: concurrent `FOR UPDATE SKIP LOCKED` single winner, deferred availability/lease expiry/stale token fencing, lost ACK **response** after committed delivery + duplicate replay, retry exhaustion/dead-letter isolation, and `pg_dump`/`pg_restore` 16 roundtrip with row-count and zero-effect checks. Installs the exact six migrations in a **new** throwaway database; drops it after tests. Only REJECT events with `SYNTHETIC_UNVERIFIED` audit fixtures are used. They are **not human approvals**.
- `.github/workflows/hitl-pg16-disposable.yml`: dedicated, path-scoped PR CI; GitHub-managed disposable `postgres:16-alpine` service and Ubuntu 24.04 job container. Installs Ubuntu `postgresql-client-16` (no sudo/host Docker), Python venv + `psycopg[binary]==3.2.13`; verifies both dump and restore major version 16. Checks out **PR head SHA** rather than synthetic merge commit. Uploads 7-day synthetic report, dump, checksum and logs. Shared `quality.yml` untouched.
- This document only. No `app/core/main.py`, Core xref, Portal, Policy runtime, Worker runtime, release manifest, LIVE, executor, SSH, Ansible, sudo, GLPI write, deploy or main push.

**Run command (dedicated GitHub Actions job only):**

```sh
/tmp/hitl-venv/bin/python -m unittest discover -s tests -p 'test_hitl_pg16_candidate_outbox.py' -v
pg_dump --version && pg_restore --version
sha256sum /tmp/hitl-pg16-dr.dump
```

Gates: `GITHUB_ACTIONS=true`, `AIOPS_CI_OUTBOX_DISPOSABLE=YES`, URL exactly `postgresql://aiops:<CI-only password>@postgres:5432/aiops`; PostgreSQL major 16; exact pinned SQL blob SHA. A failed gate aborts. All data and the dump are synthetic. If Ubuntu package installation fails, **do not drop DR**: use a separate reviewed versioned job image `postgres:16.15-bookworm` with Python installed inside that isolated job container, and rerun the same PG16 tests/DR and exact-head CI; never silently fall back to PostgreSQL 15.

## Proof boundary and remaining gate

| Claim | This PR |
|---|---|
| SQL-model concurrency, lease expiry, lost response, duplicate, retry/dead-letter | Pending exact-head disposable PG16 CI; does **not** exercise Core handler |
| Installed 009–012 + PG16 `pg_dump`/`pg_restore` | Pending dedicated exact-head CI; prior #234 3/3 migration gate observed |
| Core real claim/ACK HTTP and Worker delivery | **NOT_TESTED** on candidate; candidate lacks #194 Core claim/ACK endpoints |
| Worker application restart / Temporal server restart while in-flight | **NOT_TESTED** on candidate; no #194 workflow port and no disposable Temporal stack here |
| Actual packet loss during ACK | **NOT_TESTED** (only discarded response model) |
| Production IncidentWorkflow | **NOT_TESTED** |
| Real OIDC/MFA/GLPI actor authority | **NOT_ATTESTED** |
| DEMO/SIMULATE effects | `execution_allowed=false`, `effect_allowed=false`; zero `effect_receipts` in isolated database |

**Do not promote this SQL model to runtime proof.** It verifies PostgreSQL semantics and restore, not Core's API implementation. A Temporal signal is a notification, **never authorization**. Synthetic REJECT is not an authenticated human decision. No synthetic APPROVE, LIVE or remediation is exercised.

**Next dependency (Core/architect):** agree Core-owned outbox claim/ACK handlers, authenticated tenant/Run/proposal hash/revision/lease fencing, 009–012 migration compatibility, and exact Core `main.py` ownership before selectively porting production code from #194/#204. Only then add disposable Core HTTP → Worker → Temporal restart and lost-network-ACK failure injection on a new exact candidate SHA. Preserve strict Policy HTTP and independent executor prohibition.

**Rollback:** close this Draft PR or revert only its three test/workflow/doc files; no schema migration or runtime code change. CI drops isolated databases, 7-day artifact expires. No main reset or persistent-data rollback.
