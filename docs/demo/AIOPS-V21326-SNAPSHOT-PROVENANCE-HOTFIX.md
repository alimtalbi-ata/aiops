# AIOps V2.13.26 — Snapshot metadata trust hotfix (GitHub branch)
**Status: isolated source correction only; no runtime screenshot, production deployment or business validation.**

The original STAR choreography returned `verified_real_capture=true` whenever the user supplied a `captured` metadata record. This was a false attestation: a SHA-256 string, path and URL alone do not prove that a screenshot was taken from the intended authenticated application or run.

The patched `demo/star_snapshot_choreography.py` returns `metadata_complete=true` for such records, but **always** returns `verified_real_capture=false`. `tests/test_star_snapshot_choreography.py` now explicitly tests that distinction. The new `star-snapshot-metadata-offline.yml` workflow executes only local unit tests and syntax compilation.

This branch-only correction must not be confused with the V2.13.26 **offline temporal gate candidate**. That candidate remains in a separate patch until the missing V2.13.21–25 modules have been reconciled. No Chromium qualification of the deployed STAR asset, no n8n/Grafana/GLPI capture, and no HITL approval has been performed by this hotfix.

Safety: preserve main, keep the PR draft, no auto-merge; no changes to Debian, the portal at port 17777, GLPI V1 :8080, n8n, Grafana, the V1 bridge, tickets, CMDB or remediation. To roll back, revert the branch commit; no production rollback is needed.
