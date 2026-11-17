# AIOps2 integration ADR — 2026-11-01 08:48 CET

**Decision:** selective source-only port to sole Draft #234. **Status:** D0 exact-head pending; D1/D2 NOT_QUALIFIED, D3 NO_GO, D4 NOT_ATTESTED. No main merge.

**Base/main:** `ae7c3e5102b99a66bd7806d602146f1309a9749d`; prior candidate `ba009821abec50cc52dcbea1e8c6d71b58966115` D0 7/7, not transferable. Focused product commit `c3e6b4e8ae8448d0295f369509aa2cb8976ce557` selectively imports 12 exact source blobs: #268 ACME 3; #269 Portal 3; #270 Core native TLS 3/5; #271 Worker 3. All source PRs Draft and stacked on old #234, left open for provenance. Main-based candidate is the only integration target.

**Source qualification:** #268 [Quality 41283394088](https://github.com/alimtalbi-ata/aiops/actions/runs/41283394088) 3/3, ACME 138/138; #269 [Quality 41283838658](https://github.com/alimtalbi-ata/aiops/actions/runs/41283838658) 3/3, Chromium 16/16 + consumer 22/22; #270 [Quality 41284915846](https://github.com/alimtalbi-ata/aiops/actions/runs/41284915846) 3/3, Core 84/84 + native TLS 9/9, PG16 14 PASS/1 SKIP; #271 [Quality 41285129060](https://github.com/alimtalbi-ata/aiops/actions/runs/41285129060) 3/3 and [combined 41285129105](https://github.com/alimtalbi-ata/aiops/actions/runs/41285129105) 1/1, 7/7 + PG16 5/5. Source qualification is not integrated exact-head proof.

**Explicit holdback:** #270 native same-major PG16 SHA256 archive/restore test and its migration-suite loader NOT ported because source CI skipped missing `/usr/lib/postgresql/16/bin/pg_dump`. Require a dedicated disposable PG16 client workflow and zero skips before port. Preserve 013 immutable nonce/revocation audit; no DROP or live migration.

**Threats and limits:** no authenticated ACME Incident/Run/GLPI/Evidence readback; no independent GLPI human rights or signed ALLOW; no Core business GET on Portal UNKNOWN; no production Worker or physical network partition; synthetic HMAC is not human authority; Temporal signal is notification only. No external writes, host/SSH/sudo, Docker socket, LIVE executor. D0 rerun after final documentation commit, D1/D2 full journey and D3 kit remain unqualified.

**Revert:** create new revert commits for product `c3e6b4e8ae8448d0295f369509aa2cb8976ce557` and this ADR/board commit, rerun exact-head CI. Do not force-push/reset main or drop audit 013.
