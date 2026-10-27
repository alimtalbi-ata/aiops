# AIOps 2.0 — V2.13.39 | STAR Chromium read-only adapter (HLD/LLD)

**Status:** code candidate integrated on the draft PR branch; qualification only against isolated synthetic HTML. **No authentic Debian screenshot, business success, HITL approval or production remediation is claimed.**

## HLD — safety boundary and intended sequence

The unique operator portal stays at `:17777` (no new listener). A canonical ingress identity (`run_id`, `correlation_id`) and the independently obtained execution/dashboard/ticket ID are the inputs to the offline STAR cue contract. The Chromium adapter is a separate operator-invoked process: validated plan → default `DRY_RUN` → optional reviewed GET navigation → exact DOM identity/state comparison → mandatory DOM masks → PNG + SHA-256 + unreviewed manifest → independent `star_browser_manifest_gate` integrity check → human review. The portal never grants LIVE permissions from a screenshot. The workflow V1 bridge and Debian services remain untouched.

The scenario storyboard covers Brocade SAN fabric P1 with Payments impact, Payments P2 and variant failures; Analyst/Critic, CMDB, Policy, HITL, **simulation-only** remediation, verification, closure and deterministic replay. The adapter observes an existing page; it neither creates tickets nor changes n8n/GLPI/Grafana/CMDB state.

## LLD — request-level controls

1. **Dry-run default:** `python -m demo.star_snapshot_browser plan.json` validates without opening Chromium, network requests or writing evidence. The plan JSON must contain the canonical identity and three exact DOM selectors; `correlation_selector` is mandatory. Duplicate JSON keys, oversized plans and unknown fields are rejected.
2. **Explicit operator opt-in:** a non-fixture capture requires both `--capture` and the environment variable `AIOPS_STAR_ALLOW_OPERATOR_READ=1`. `AIOPS_STAR_NO_RUNTIME=1` overrides the opt-in in CI. This is an additional gate, **not** authorization to access production.
3. **Exact network allowlist:** only GET for the exact top-level event URL is allowed by default. Every additional same-origin static or XHR/fetch URL must appear verbatim in `approved_get_urls` (maximum 32), explicitly reviewed by the operator. POST, redirects to other events, downloads, popups, WebSockets, cross-origin requests and unlisted same-origin GETs fail closed. Even GET can be mutating on an incorrectly designed service: production browsing still requires a separate operational risk review.
4. **Application binding:** GLPI **V1** requires `:8080/front/ticket.form.php?id=<ticket>` (not the GLPI 11 instance), n8n requires the exact execution path, Grafana requires the dashboard UID and absolute bounded time range linked to `run_id`.
5. **Proof boundary:** screenshot and manifest are `CAPTURED_UNREVIEWED`. `runtime_page_authenticated`, `business_outcome_verified`, `human_approval_authenticated` and `live_action_authorized` remain false. Timestamp alignment remains `UNVERIFIED_REQUIRES_EXTERNAL_EVENT_TIMESTAMP` until independently correlated. Masked pixels do not guarantee complete anonymization.
6. **Immutable local output:** capture uses create-only files with restrictive permissions. Existing evidence is not overwritten; failed manifest write removes the new PNG. The independent manifest gate checks PNG structure, SHA-256, chronology, cue/service, exact identities and forbids promoted claims.

## Qualification and operational limits

CI sets `AIOPS_STAR_NO_RUNTIME=1`, uses disposable synthetic HTML and never connects to Debian. Run:

```bash
AIOPS_STAR_NO_RUNTIME=1 python -m unittest discover -s tests -p 'test_star_snapshot_browser.py' -v
AIOPS_STAR_NO_RUNTIME=1 python -m unittest discover -s tests -p 'test_star_snapshot_browser_hardening.py' -v
AIOPS_STAR_NO_RUNTIME=1 python -m unittest discover -s tests -p 'test_star_*.py' -q
```

**Identity-loss diagnostic remains open:** the historical n8n 02 Webhook → RAG → Canonical Identity → Call Analyst → 03 Prepare Analyst Payload must carry the *same* `run_id` and `correlation_id`. `RUN_ID_MISSING` or contradictory IDs must block; never synthesize IDs downstream. An n8n `success` execution alone is not business validation. Investigate with sanitized, read-only stage traces, not with modifications to production workflows.

**Rollback:** revert only the PR branch files or remove local candidate artifacts after inventory. No database migration, container restart, port binding, live remediation, GLPI ticket mutation, or n8n import is part of this change. Main is never merged automatically.
