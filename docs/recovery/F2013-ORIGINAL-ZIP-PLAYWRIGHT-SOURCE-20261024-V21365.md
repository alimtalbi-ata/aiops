# AIOps V2.13.65 — F20.13 complete historical capture sources recovered (private ZIP evidence)

## Provenance — verified from original Library ZIP bytes on 2026-10-24

Three **private** original ZIPs were materialized into an isolated workspace, opened read-only and checked using `ZipFile.testzip()` (CRC PASS for each). Their exact SHA-256 fingerprints and source-member hashes were computed from the original bytes, **not** reconstructed from chat transcripts. Original ZIPs, PNGs, browser profiles, tokens and raw historical source files are **not committed**.

| Original archive | Original ZIP SHA-256 | CRC | Source findings |
| --- | --- | --- | --- |
| `AIOps-UCP-F20.13-EVIDENCE-DEMO-KIT-v0.1.zip` | `9e131bd42256318bfea2a2caf3b90eb1a93ce5911ec8745fbcc12cbac0d696a7` | PASS | Shell capture/qualification, schema and documents; no Python source |
| `AIOps-UCP-F20.13-EVIDENCE-DEMO-KIT-v0.2-RELEASE.zip` | `ab30e200e4299d9151d1043dcf368cf90a08aab0ac7f2fd7dc788c65275aa046` | PASS | One complete packaged Python script, `scripts/capture-evidence-v02.py` |
| `AIOps-UCP-F20.13-DEMO-MULTISTACK-KIT-v0.3.zip` | `cc2fdc0f1d7b2b3e82937925030d7dbb978fe341f4ed2d74030e59462a7190f1` | PASS | One complete packaged Playwright Python script, `scripts/capture-multistack.py` |

Source-member paths below are relative to their versioned ZIP root:

| Version and original member path | Bytes | Lines | SHA-256 | Static qualification |
| --- | --- | ---: | --- | --- |
| F20.13 v0.2 `scripts/capture-evidence-v02.py` | 1,792 | 44 | `df4cb45cd32d37d136280752a2a9fdeae661c6b51c8b1c6463d1ca0ac5fb3513` | Complete packaged member bytes, Python AST PASS; runtime NOT executed |
| F20.13 v0.3 `scripts/capture-multistack.py` | 3,928 | 46 | `bc8fb46e81d37cb90f64d53feaa7e14171aa65e0137a0143650ba04d12e623ee` | Complete packaged member bytes, Python AST PASS; runtime NOT executed |

**Precise completeness boundary:** the two files above are complete *members of their respective original ZIPs*. This does not prove that either historical application, its external dependencies or the F20.13 campaign was complete. The separately named `scripts/demo-multistack-capture.py` and `playwright-evidence-campaign-full.py`, referenced by the 15 October shell transcripts, are **not contained in these three ZIPs**; their complete original bytes remain to be recovered. Do not conflate `capture-multistack.py` with `demo-multistack-capture.py`.

## Business intent, interfaces and architecture

- **v0.2 baseline collector:** invokes local Chromium by `subprocess` against the legacy UCP root (default `127.0.0.1:8141`), writes a baseline PNG and manifest. It explicitly records that the 13 SPA views were **not** navigated or individually validated. Its `real=True` manifest attribute is not an authenticated runtime/business attestation.
- **v0.3 multistack collector:** imports Playwright, launches Chromium, navigates 12 legacy UCP SPA views via `nav button[data-id=...]` and checks active button plus nonempty workspace/content. It probes Grafana `:3000`, n8n `:5678` and GLPI `:8080` using `curl` and captures external landing pages. The resulting PNG/video/manifest may include authentication screens, URLs and other private data. It does **not** prove an incident/ticket/workflow/dashboard was displayed, nor bind a canonical `run_id`, `incident_id`, `ticket_id`, event timestamp and screenshot SHA to nine STAR checkpoints.

Historical dependencies: Linux Chromium executable, Playwright Python, legacy UCP SPA DOM selectors, optional `curl`, local filesystem and reachable external services. There are hardcoded Debian-specific executable paths and output directories. No dependency or selector compatibility with the current `:17777` portal has been demonstrated.

## Comparison to current PR #36 — reuse decision

The current `demo/star_snapshot_browser.py`, `demo/star_browser_manifest_gate.py`, `demo/star_snapshot_choreography.py`, and `demo/star_checkpoint_reconciliation.py` already provide stricter isolated capture and canonical checkpoint identity contracts. The legacy v0.3 script is **quarantined**: do not copy its unguarded external probes, absolute paths, video capture, `real_only` claim, manifest URLs or write-on-run behavior into the modern portal.

Potentially reusable **design knowledge only**, pending tests: the 12 legacy SPA domain identifiers (`operations`, `incidents`, `timeline`, `evidence`, `ai_decision`, `knowledge_rag`, `cmdb`, `observability`, `automation_hitl`, `replay_chaos`, `reports_kpi`) and the old active-navigation selector pattern. The nine modern STAR checkpoints are a different contract; mapping is **not one-to-one** and must be tested with synthetic HTML, not assumed.

The v0.2 baseline capture script is also quarantined: it captures only one page, uses `--no-sandbox`, writes to an operator-chosen directory, and has no authenticated business evidence. The existing modern read-only Chromium collector is preferred. Do not duplicate these old collectors.

## Conditions for reuse, tests and rollback

1. Keep original ZIPs and all generated reports private. Check exact archive/member SHA-256 and CRC, and inspect for secrets and private screenshots before any use.
2. Compare source SHA-256 against a pinned clean checkout using `zip_source_recovery` + `zip_reuse_compare` (now including nested sources); exact-byte matches are not permission to import.
3. Extract only declarative view/selector knowledge after review. Add isolated Chromium fixture tests that assert the **correct application screen**, canonical identity and fail-closed 02→03 handoff; explicitly reject login pages and synthetic-as-real claims.
4. Never run historical collectors on Debian production, start/stop containers, probe LIVE applications or write GLPI/n8n/Grafana/DB/CMDB. Runtime E2E on `:17777` remains unqualified by this recovery.
5. Rollback of the present cycle: revert the comparator, its synthetic tests and this documentation from PR #36. No runtime rollback, migration or port changes are needed.

This file documents recovered historical **original member bytes and static findings**, not restored operational F20.13 functionality or a successful E2E release.
