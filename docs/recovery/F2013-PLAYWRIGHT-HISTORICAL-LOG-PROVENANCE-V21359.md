# F20.13 Playwright heritage — recovered logs, not recovered executable sources

Status: **HISTORICAL_LOG_VERIFIED / ORIGINAL_SOURCE_MISSING** (2026-10-24). This is a provenance record, not an approval to import, deploy, or capture.

## Original artifacts inspected (read-only)

| Original Library filename | Library file ID | Raw bytes | SHA-256 |
| --- | --- | ---: | --- |
| `Texte collé(20261015-154001).txt` | `file_0000000017d8820ab046f5b90b67ff4a` | 16475 | `ec0761cbc5243e0d89ccbb63b27754d3d7bea748b13a5b41a0dac66f735e4401` |
| `Texte collé(20261015-155749).txt` | `file_00000000c83c820eac2dffb697747e40` | 19525 | `65611d3d0cc4abe26e958281dbaf854543d3c14c80a8c8036d60d79cc5f1aa12` |

These are user-provided command logs dated 2026-10-15, **not the executable original files**. No raw log or screenshot is committed. Their hashes identify only the logs.

## Historical context, business need, architecture

Historical kit: `AIOps-UCP-F20.13-EVIDENCE-DEMO-KIT-v0.2`. Reported source path: `scripts/demo-multistack-capture.py`; Python Playwright/Chromium. Purpose: capture UCP portal views and application screenshots for a guided multi-stack demo. Original UCP was on port **8141**, not the current single-portal target **17777**. Historical downstream services: GLPI **8080**, n8n **5678**, Grafana **3000**, plus Kibana **5601** and Prometheus **9090**. These are historical references, not instructions to open ports or access production.

The October 15 log contains a visibly **truncated source creation block** (corrupted after the service list), followed by patch commands and capture results. It cannot be reconstructed as a complete safe source tree. The source filename is a *lead* for archive recovery, not an imported module.

## What the logs actually demonstrate

- One F20.13 Playwright evidence manifest reported **11/13 PASS**, with screenshot timeouts for `ai_decision` and `knowledge_rag`. Reported screenshot SHA-256 values are not independent byte checks without original PNG files.
- The later multistack log reported **17 PASS, 0 FAIL, 0 HTTP_ERROR** after selector fixes for `automation_hitl` and `reports_kpi`, and after allowing non-UCP services to be captured. This is a historical log claim, **not a newly executed test**.
- The historical GLPI capture reported page title **“Authentication - GLPI”**, and n8n title **“n8n.io - Workflow Automation”**. An HTTP 200 or browser screenshot of a login/landing page **does not** prove an authenticated ticket or a specific n8n execution. No `run_id`/`incident_id`/`ticket_id` binding is established by these logs.

## Interfaces, dependencies, reuse conditions and test plan

Dependencies: Playwright, Chromium, historical portal DOM selectors and service access. No credentials or sessions were recovered or should be published. Before reuse, recover the exact full `scripts/demo-multistack-capture.py` from a verified ZIP/backup, pin its SHA-256, scan for secrets, compare it with the current `demo/star_snapshot_browser.py` and checkpoint plan builder, and import only distinct reviewed behavior. Use a **read-only, synthetic** browser environment for testing. Require exact service view, independently sourced IDs, provenance, screenshot SHA-256, timestamp, redaction and nine-cue deterministic replay; reject login/landing pages as ticket/execution proof. No write operations and no LIVE remediation.

## Rollback

Documentation only; delete/revert this record if an authoritative original archive contradicts the logs. Never change the Debian runtime or its V1 containers to recover these sources.
