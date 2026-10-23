# AIOps STAR V2.13.39 — Browser GET request fence (HLD/LLD, 2026-10-23)

**Scope:** Pure Python, offline request-policy contract on the draft PR. No Chromium runtime navigation, production capture, service restart, ticket/CMDB write, or LIVE remediation was performed by this change.

## HLD: proof and control boundaries

The single user portal remains on port **17777**. The ACME STAR storyboard is unchanged: Brocade SAN P1 impacting Payments, Payments P2, Analyst/Critic, Policy, HITL, **simulated-only** remediation, verification, closure and deterministic replay. Each application cue must reference the exact n8n execution, Grafana dashboard/time window, or **GLPI V1 on port 8080**. The browser adapter is an optional, separate read-only observer; it cannot attest business success or human approval.

The new `demo/star_browser_request_fence.py` supplies a pure request filter for the pending local Chromium adapter. It is deliberately independent of Playwright and has **zero** HTTP/DNS effects. The adapter itself remains an **offline candidate** until integrated and tested on the exact PR SHA.

## LLD: fail-closed request policy

`ReadOnlyRequestPolicy(event_url, allowed_origin, reviewed_get_urls=())` permits a **GET of the exact top-level event document** only. A secondary same-origin GET (including XHR/fetch, images, CSS and scripts) is denied unless its complete URL was individually approved in `reviewed_get_urls` (max 32 distinct entries). Cross-origin requests, credential-bearing URLs, URL fragments, POST, unexpected navigation and unapproved event IDs are denied. The caller must abort and record all denied requests.

The policy is a filter, not a browser authentication mechanism. **GET may still have side effects on a poorly designed service.** A human security review and explicit authorization are mandatory before using a real operator browser. A successful filter check does not establish event-time alignment, anonymity, provenance, HITL approval or business validation.

## QA and limits

Run `AIOPS_STAR_NO_RUNTIME=1 python -m unittest discover -s tests -p 'test_star_browser_request_fence.py' -v`. The seven synthetic tests cover exact navigation, POST, same-origin unlisted GET, cross-origin URLs, allowlist duplicates and unsafe origins. The dedicated workflow `star-browser-request-fence-offline.yml` runs on the PR without browser or production access.

**Pending:** publish and integrate the full local `demo/star_snapshot_browser.py` adapter, qualify Chromium on isolated fixtures, verify the true n8n/Grafana/GLPI V1 pages only with operator approval, and reconcile workflow 02 Webhook → RAG → Canonical Identity → Call Analyst with workflow 03 `RUN_ID_MISSING` using sanitized traces. Never fabricate a missing `run_id` downstream; n8n technical success is not business success.

**Rollback:** revert the three branch-only request-fence files. No change to main, Debian, bridge V1, databases, tickets, network listeners or workflows.
