# RC2.0 — MariaDB Disaster Recovery Qualification

Owner: Abdelhalim Talbi. Source: PR #21, `feat/core-analysis-quality-v2`.

The MariaDB DR CI job starts an isolated disposable MariaDB 11.4 container
with Docker network disabled and a synthetic two-row dataset. It performs a
logical database dump, creates a distinct target database, restores the dump,
compares SHA-256 of ordered row content, and verifies malformed SQL is rejected.
It removes the temporary container and dump via shell cleanup traps.

The job is a required dependency of the cumulative release kit; it uploads
`reports/mariadb-dr-rehearsal.json` with a scoped result. Previous PostgreSQL,
Temporal E2E, migration and model-evaluation checks remain mandatory.

**Not qualified by this job:** actual GLPI database content, production MariaDB,
Temporal database recovery, transaction consistency across services, application
volumes, recovery-time objectives, production restore, LIVE remediation.

Acceptance is contingent on all jobs passing on the exact release commit.
