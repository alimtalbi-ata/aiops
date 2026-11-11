# Policy/HITL P0 — selective no-effect port to clean candidate

Status: **PROPOSED / NOT INTEGRATED / RELEASE_STABLE=NO_GO**. Development only.
Owner: Policy/Worker/outbox/HITL tests. This port never authorizes effects.

## Source, ancestry and ownership

- Target: architect-designated `integration/enterprise-slice-main-20261031-2230` at `ae7c3e5102b99a66bd7806d602146f1309a9749d`, initially equal to DEV main. Dedicated branch: `feat/p0-policy-hitl-noeffect-clean-candidate-20261031-2330`.
- Historical source #228: `cd703c7d92782eb3309aaec70931efda465aed0d` on obsolete #201. Only Policy evaluator, synthetic fixture and tests are reused. No wholesale cherry-pick.
- Source #204: `5285aec4359a8132cb6c5801dc8d3a18118930fc` stacked on #194 `40d38705cf2bde3be6052340442c117a81908f65`. Source Quality [41241099554](https://github.com/alimtalbi-ata/aiops/actions/runs/41241099554) 6/6, plus V2.8, Offline and Historical SUCCESS at that exact source SHA. Source PG16 14/14 and DR 32 tables PASS. These source results **do not qualify this new branch**.
- Architectural contracts: reference architecture, reuse register, execution control board and issue #186. Core owns canonical Incident/Run, approval and outbox; Temporal signals are notifications, not authority.

## Scoped port

- `app/policy/main.py`: `evaluate()` exposes explicit `execution_allowed=false` and `effect_allowed=false` for all decisions, including read-only LIVE PASS/ALLOW; `/api/policy/check` preserves the strict three-field HTTP v2.1 contract `state/decision/reason`. No Core probe relaxation.
- `app/policy/simulate_fixture.py`: read-only synthetic presentation; `SYNTHETIC_UNVERIFIED` and both no-effect flags, no authenticated human approval.
- Tests: `test_policy_safety.py`, `test_policy_simulate_fixture.py`, `test_policy_real_http_integration.py`, and `test_policy_core_xref_boundary.py`. The last is an **offline negative xref-shaped contract**, not a real Core xref integration. It verifies caller-supplied xref claims cannot promote a Policy decision.
- `.github/workflows/quality.yml`: only two additional test steps in the existing quality job. Preserve existing PostgreSQL 16 Core/NOC and Grafana jobs; no new workflow engine, migration, Portal, Core xref or release manifest.

## Parent-dependent work explicitly deferred

#204 Worker/Temporal and PG16 outbox tests require the **full Core-owned 009→010→011→012 migration and API chain**, including OIDC, proposal revision/hash, lease token, fencing, tenant/SoD, claim/ACK and rollback. #194 contains 009/010/011; #204 has no 012. Core #233 is a separate candidate xref proposal, **not** proof of an applied 009→012 chain. Never copy 011 or 012 alone. The target candidate does not currently qualify this chain.

- PostgreSQL 16 outbox concurrency, lease expiry, lost ACK, duplicate, retry/dead-letter and Worker/Temporal restart: **NOT_TESTED on this port**; historical #204 `OBSERVED_CI_DISPOSABLE` only.
- Real Core xref HTTP/DB and tenant ownership: **NOT_TESTED on this port**; offline adversarial xref-shaped payload is **not** a runtime substitute.
- Real OIDC/MFA identity: **NOT_ATTESTED**. Production IncidentWorkflow and real network ACK loss: **NOT_TESTED**.
- No signal Temporal, fixture actor, boolean approval or Policy PASS grants execution. All synthetic paths must remain `execution_allowed=false`, `effect_allowed=false`; real effect receipts: zero.

## Reproducibility and rollback

On Python 3.12 with pinned `fastapi==0.116.1`, `pydantic==2.11.7`, `httpx==0.28.1`:
```sh
python -m unittest discover -s tests -p "test_policy_safety.py" -v
python -m unittest discover -s tests -p "test_policy_simulate_fixture.py" -v
python -m unittest discover -s tests -p "test_policy_core_xref_boundary.py" -v
```
The existing CI Core/PostgreSQL 16 job starts the real Policy service on loopback and runs `test_policy_real_http_integration.py` plus `test_core_demo_policy_real_integration.py`. This is **not** a 009–012 outbox qualification. Existing DR must not be removed. If PostgreSQL client installation fails on a future integration, separately pin and qualify a PostgreSQL 16 client/psycopg alternative and keep DR.

Handoff requires exact new HEAD CI/job counts, artifact URL/checksum if present, and limits. Rollback: revert this single scoped commit or close the draft PR. No DB migration, LIVE remediation, executor, SSH, sudo, Ansible, GLPI write, deploy, merge or main push.
