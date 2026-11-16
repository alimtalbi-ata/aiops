# AIOps 2.0 — RC1.5 release archive hardening (2026-10-20)

**Owner:** Abdelhalim Talbi. **Change branch:** `feat/core-analysis-quality-v2`. **PR:** #21.
**Prior qualified baseline:** RC1.4, GitHub Actions run #39402204564 (5/5 jobs).

## Purpose
A valid SHA-256 checksum or ZIP CRC does not establish that an archive is safe to process.
A malicious or misbuilt kit could contain symlinks, encrypted entries or unbounded
decompression content, even when its outer checksum and file manifest are internally
consistent.

## Implemented release gate
- Fail closed on ZIP symlink members and encrypted entries.
- Bound archive entry count (10,000), each uncompressed file (128 MiB), total
  uncompressed members (1 GiB), and suspicious compression expansion (>250:1
  for members exceeding 1 MiB).
- Apply metadata limits **before** CRC content expansion.
- Preserve existing SHA-256, per-member manifest, path, qualification-state and
  synthetic-vs-real-model verification semantics.
- Add adversarial tests for checksum-valid symlink and high-expansion content.
- Run the verifier test suite as a mandatory quality-build CI step.

## Qualification states
This document records an implementation, not a passing CI result.
RC1.5 may be called qualified only after the exact head commit passes the
full workflow, including all database, temporal runtime and release-kit jobs.
Real-model and production validation remain NOT_RUN. LIVE remediation remains disabled.

## Next batch
1. Full disposable restore rehearsal with crash/restart injection and ownership guards.
2. Held-out real-model Analyst/Critic evaluation with explicit quality thresholds.
3. Authenticated read-only connectors for CMDB, metrics and change intelligence.
4. Immutable, approval-bound action proposal and fencing state machine;
   do not implement destructive LIVE effects until separately qualified.
