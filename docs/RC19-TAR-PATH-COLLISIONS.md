# AIOps 2.0 RC1.9 — ordered TAR extraction safety

**Author:** Abdelhalim Talbi. **Date:** 2026-10-20. **Branch:** `feat/core-analysis-quality-v2`, PR #21.
**Previously qualified baseline:** RC1.8 — Actions #39411707688, all jobs PASS.

## Change
Volume TAR validation now rejects file/directory ancestor collisions independently
of member order. Both `./parent` followed by `./parent/child` and the reverse
order are unsafe because extractors may overwrite, fail, or interpret the path
differently. A matching SHA-256 does not make such an archive safe.

Two adversarial regression tests reproduce both forms; existing positive tests
keep ordinary files, directories, and `./` root metadata valid. The existing
CI quality job runs the backup verification unit tests.

## Qualification boundaries
The implementation has been committed; RC1.9 acceptance is conditional on
the exact head commit passing all required CI jobs. No full multi-service restore,
production disaster recovery or application-consistency claim is made. No LIVE
remediation or non-isolated restore is authorized.

## Next major engineering milestone
Create a **disposable full-stack restoration rehearsal** with independent
PostgreSQL, Temporal persistence/visibility, MariaDB, and volume fixtures,
reporting measured restore times, corruption injection results and each
service's post-restore health without accessing the production Debian host.
