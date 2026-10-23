# AIOps STAR V2.13.33 — PNG evidence integrity gate (23 October 2026)

**Status:** offline integrity hardening on draft PR #36; no Debian/runtime capture, production deployment, HITL approval or live remediation. This is NOT runtime provenance authentication.

## Defect and correction

Previously `demo/star_capture_evidence.py:inspect_png` accepted a PNG-like file after checking only its first 24 bytes, a signature, IHDR marker and nonzero dimensions. A fake or truncated file with a matching SHA-256 could therefore receive `integrity_checked`. The new `demo/star_png_integrity.py` validates the PNG container in bounded streaming mode before SHA comparison, and the collector imports it.

## HLD

Operator-authorized browser session (not implemented here) → screenshot stored under evidence root → untrusted manifest with canonical `run_id` and expected SHA-256 → metadata and path containment gate → bounded PNG structural/CRC gate → SHA-256 comparison → ordered cue manifest. All results remain `runtime_authenticated=false`, `business_validated=false`, `human_approval_authenticated=false`, `live_action_authorized=false`.

No additional listener/port, no write to n8n, Grafana, GLPI, CMDB, ticket, Debian service, bridge or production workflow. The portal remains exclusively :17777. The GLPI V1 evidence target remains :8080, never :18080.

## LLD / fail-closed checks

- Strict PNG signature, first 13-byte IHDR, legal dimensions/bit depth/color format, <= 16,384 per axis, <= 16,777,216 pixels.
- Streamed chunk framing and CRC32; reject malformed lengths, invalid chunk names, unknown critical chunks, duplicate IHDR, noncontiguous IDAT, missing IDAT/IEND, trailing data.
- Reject embedded PNG text metadata (`tEXt`, `zTXt`, `iTXt`) to reduce risk of leaking secrets. PNGs containing these chunks require sanitization outside production before qualification.
- Max file size 15 MB; SHA-256 calculated on the exact read bytes; no image decoding or zlib decompression, so CRC integrity is NOT proof that pixels decode, nor that the right application page was visited.
- Existing manifest, identity, timeline and claim firewalls are unchanged; fake IDs must never be created downstream.

## Verification

Local isolated Python checkout reconstructed from the fetched collector contract: `python -m unittest discover -s tests -p 'test_star*py' -v` → 20 tests PASS (14 PNG parser tests, 6 collector tests); `python -m compileall -q demo tests` → PASS. Synthetic fixtures only. GitHub CI must be evaluated on the new exact SHA independently; no claims about Debian Chromium or production captures.

## Rollback and promotion

Revert only this feature's commits on the PR branch if PNG compatibility breaks; never revert main or modify the running stack. Promotion requires passing PR CI, review of accepted real PNG variants, isolated Chromium verification of actual n8n/Grafana/GLPI V1 pages, timestamp/run/execution/ticket identity linkage and human review. Keep the PR draft; no automatic merge.

## Open work

Workflow 02 Webhook → RAG → Canonical Identity → Call Analyst and workflow 03 `Prepare Analyst Payload` `RUN_ID_MISSING` require redacted read-only export/traces to locate the first identity loss. Successful n8n HTTP/execution status alone never constitutes business validation.
