# STAR Legacy PNG forensic verification

`demo/star_legacy_png_verify.py` performs read-only **byte integrity** verification of historical F20.13 Playwright PNG assets against SHA-256 declarations, using the existing bounded `demo.star_png_integrity.inspect_png` validator (PNG signature, chunk order, CRC, size, metadata restrictions).

Inputs: historical `PLAYWRIGHT-EVIDENCE-MANIFEST.json` or `DEMO-MULTISTACK-MANIFEST.json`, an operator-local evidence root containing original PNG filenames. No network or application access. Rejects symlinks, traversals, malformed names, and unsupported legacy manifests; historical absolute screenshot paths supply only a basename. Reports omit URL/contents and retain `runtime_authenticated=false`, `business_state_verified=false`, and `eligible_for_star_proof=false` **even for an exact SHA match**.

Tests use a 1×1 synthetic valid PNG (not a real screenshot): exact match, wrong checksum, and symlink refusal. CI workflow `star-capture-evidence.yml` runs tests for this module.

**Meaning of the result:** matching PNG bytes establish only that the file corresponds to the historical declaration; they do not prove the login status, application page, run identity, time, HITL decision, or current runtime behavior. Never auto-import these matches as STAR runtime evidence. Follow up with authorized, isolated Chromium capture of exact n8n execution / Grafana alert panel / GLPI ticket and independent event-to-capture linkage. No changes to Debian V1 or portal :17777.
