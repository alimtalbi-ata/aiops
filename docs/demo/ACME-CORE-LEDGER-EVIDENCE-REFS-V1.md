# Core synthetic AI Ledger Evidence References v1

Owner: NOC/Copilot. Status: **candidate, NOT_READY_FOR_STABLE**. Depends on #145 → #149 → #154.

## Endpoint (internal only)

`GET /api/noc/runs/{rid}/evidence-refs` on Core. Bearer `AIOPS_INTERNAL_TOKEN` required **before SQL**. Never call this endpoint directly from a browser or put the internal token in Demo Studio JavaScript.

Success `200` (`aiops.core-demo-evidence-refs.v1`) returns `run_id`, `classification=SYNTHETIC_ONLY`, `event_link_verified=true`, `tenant_acl_qualified=false`, `runtime_attested=false`, and bounded `items[]` with `evidence_id`, `source`, `payload_sha256` and `known_at`. No raw payload, prompt, tenant identifier, source URL or credentials.

The resolver checks **actual PostgreSQL rows**: DEMO/REPLAY/STORY Run, matching nonempty Analysis and Critique evidence ID sets (max 80), evidence row existing, Run event containing the ID, explicit `provenance.run_id` match, `synthetic=true`, `observed=false`, 64-character SHA-256 digest and a timestamp. Any missing, conflicting, tenant-scoped or LIVE source fails closed `503` with generic detail; missing/incorrect bearer yields `401`.

This proves **internal referential provenance for synthetic CI/demo data only**. It does **not** verify the original bytes against the stored hash, assert tenant ACL, establish causal SAN→Payments impact, validate Grafana observations or prove LIVE. A fabricated but self-consistent synthetic source is not externally attested.

## Integration contract for #145/#149/#154 and schedule 5/5

The existing viewer-authenticated Portal route `/api/demo-studio/runs/{rid}/ai-ledger` is unchanged in this micro-lot; it **does not yet consume this resolver**. Before exposing a `supported=true` claim as verified evidence, a later server-side Portal adapter must reconcile every supporting ID against this endpoint and keep `runtime_attested=false`. A missing resolver response is UNKNOWN, not an empty successful evidence set.

Existing deployment script from #143/#146 copies only Demo Studio portal files and injects `main.py`: **this Core module and Core registration are not deployed by that script**. The schedule 5/5 release owner must explicitly qualify Core image/version compatibility, service deployment coverage, rollback and a post-deployment read-only smoke test before any promotion to `deploy/aiops2-stable`. No Debian/cron result is claimed here.

## Qualification

The existing `.github/workflows/quality.yml` `database-migrations` job runs real Core HTTP and PostgreSQL 16; the extended `tests/test_demo_ledger_real_http.py` checks 401, positive synthetic event-link, cross-Run/LIVE/missing data 503, tenant metadata 503 and no payload/secret leakage. No extra workflow, fake Core, real NGX, production credentials or LIVE mutation. Check the exact PR SHA and GitHub run before claiming PASS.

**NOT_TESTED:** tenant A/B actor-scoped RBAC, browser Portal consumption, real SAN/Payments metrics, Twin runtime impact, Ollama 4B, Debian applied.sha, rollback execution, post-deployment smoke, screenshots and video.

## Temporal integrity addendum — candidate #167 (2026-10-28)

The Core resolver now refuses a synthetic Evidence row whose `known_at` is
timezone-naive or more than five minutes in the future relative to the Core
clock. This is a **clock-skew safety bound**, not an attestation of freshness,
source authenticity or SAN→Payments causality. A future timestamp yields
HTTP 503 without leaking Evidence IDs. The existing endpoint and
`aiops.core-demo-evidence-refs.v1` response schema are unchanged.
