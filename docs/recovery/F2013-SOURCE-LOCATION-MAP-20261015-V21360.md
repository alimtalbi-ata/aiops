# Historical F20.13 source-location map — 15 October 2026 (V2.13.60)

## Provenance and scope
- Original Library record: `Texte collé(20261015-202457).txt`, 48,531 bytes.
- SHA-256 **of the original log file**, **not of any Python source**: `0054cfe1ae45ea072c6a839fd4eb24411546d715f133337b2c7a379d52d3cb37`.
- Observation: command output recorded historical **file paths** on an AIOps Debian host and a browser probe. This document is a **source-location lead only**. The complete source bytes, their hashes, importability, and runtime behavior have NOT been recovered or verified.
- No credentials, sessions, screenshots or original raw log are committed.

## Source leads — relative to the historical workspace
| Original version / workspace | Relative source path | Context and business use |
|---|---|---|
| F20.13 Evidence Demo Kit v0.2 | `scripts/demo-multistack-capture.py` | Cross-application evidence capture |
| F20.13 Evidence Demo Kit v0.2 | `scripts/demo-video-capture.py` | Demo video capture |
| F20.13 Evidence Demo Kit v0.2 | `scripts/capture-evidence-v02.py` | Evidence collection |
| F20.13 Evidence Demo Kit v0.2 | `scripts/playwright-demo-screens.py` | Chromium/Playwright screenshots |
| F20.13 Evidence Demo Kit v0.2 | `scripts/playwright-evidence-campaign-full.py` | Full evidence campaign |
| F20.13 Evidence Demo Kit v0.2 | `scripts/playwright-evidence-campaign.py` | Evidence campaign |
| F20.13 Demo Multistack Kit v0.3 | `scripts/capture-multistack.py` | Alternate capture implementation |
| F20.13 Client Demo Kit v0.5 | `scripts/demo-story-v05.py` | Demo storyline |
| F20.13 Client Demo Kit v0.5 | `scripts/demo-story-v06.1.py` | Revised storyline |
| F20.13 Client Demo Kit v0.5 | `scripts/demo-portal-v06.2.py` | Portal walkthrough |
| F20.13 Client Demo Kit v0.5 | `scripts/demo-portal-v06.3.py` | Revised portal walkthrough |
| F20.13 Client Demo Kit v0.5 | `scripts/evidence-validator-v06.py` | Evidence validation |
| F20.13 Client Demo Kit v0.5 | `scripts/generate-subtitles-v05.py` | Presentation subtitles |
| F20.10.1 / F20.11.1 / F20.12 Unified Workspace | `app/main.py`, `app/static/index.html` | Historical portal FastAPI + HTML |

Original root names recorded in the log:
- `ucp-f20.13-v02/AIOps-UCP-F20.13-EVIDENCE-DEMO-KIT-v0.2`
- `ucp-f20.13-demo-v03/AIOps-UCP-F20.13-DEMO-MULTISTACK-KIT-v0.3`
- `ucp-f20.13-demo-v06/kit-base/AIOps-UCP-F20.13-CLIENT-DEMO-KIT-v0.5`
- `ucp-f20.10.1/AIOps-UCP-F20.10.1-UNIFIED-WORKSPACE-KIT`
- `ucp-f20.11.1/AIOps-UCP-F20.11.1-UNIFIED-WORKSPACE-KIT`
- `ucp-f20.12/AIOps-UCP-F20.12-UNIFIED-WORKSPACE-KIT`

## Historical UI observation (not a current E2E qualification)
The log contains a Playwright probe of a former Unified Incident & Resilience Portal on **loopback port 8099**, using the `Customer Demo` button and the `#demo` fragment. Observed headings include `Evidence Center`, `Replay Center`, `HITL`, `CMDB`, `Audit Center`, `Qualification Center`, and positive/negative demo contrast. The shell-transcribed script has damaged/truncated lines and must **not** be treated as a complete executable source. This is **not** a qualification of today's unique portal `:17777`.

## Architecture, dependencies, interfaces — hypotheses requiring source inspection
- Likely Python Playwright/Chromium for screenshot scripts; FastAPI/HTML for legacy portal. Versions, exact imports, authentication, and APIs **unknown** until original files are recovered.
- Historical capture targets documented elsewhere: GLPI :8080, n8n :5678, Grafana :3000. No access attempted here.
- Proposed integration: only reuse complete scripts after checksum inventory, static secret scan, dependency inspection, unit tests, isolated Chromium qualification, route/view identity check, and explicit read-only network fence.
- Never copy raw historical cookies, auth profiles, session storage, tokens, private data, or PNGs to GitHub. No direct reuse of old production ports or live remediation.

## Recovery decision and test plan
1. Search available offline archives and already indexed recovery exports for these **exact relative paths**. No production Debian scan, shell, deployment, or service change is authorized by this note.
2. For each actual file recovered, record original ZIP/version/member path, byte count, SHA-256, matching current Git blob or duplicate, purpose, imports, interface and test coverage. Mark unavailable files as **NOT_RECOVERED**; never assign a made-up source hash.
3. Compare recovered full source against `demo/star_snapshot_browser.py`, `demo/star_browser_manifest_gate.py`, `demo/star_checkpoint_plan_builder.py`, and existing demo director / replay code. Import only non-duplicated, independently useful functionality via a draft-PR review.
4. Qualify GLPI ticket page (not login page), exact n8n execution, Grafana dashboard, run/correlation/event identity, redaction and SHA-256 on isolated synthetic fixtures before any operator read-only validation.

## Rollback
This document is informational and does not modify runtime. Revert its single draft-branch commit if its source provenance is superseded by verified archives.
