# AIOps V3 — immutable laboratory kit

**DISPOSABLE LAB ONLY — NO production or LIVE authorization.**

The assembler consumes the verified nine-image Linux AMD64 OCI BOM from the local disposable registry and produces one build-free Compose file, schema and seed SQL, a file-integrity manifest and the qualification scripts. No credentials, source checkout, Docker socket mount or image layers are included. The only published port is loopback GAMMA 18080. HITL is embedded in GAMMA, not a separately deployed service.

The registry at 127.0.0.1:15080 must still serve the exact manifest digests. The prepared runner must already have rootless Docker, Compose, Python 3 and the dedicated daemon under /tmp/aiops-v3-rootless-ci/docker-data. This package is **not** an offline image archive or a release suitable for a customer's host.

## Independent qualification

The CI assembles once, copies the identical bundle into install-1, install-2 and install-3 under its dedicated root, and invokes install-ci.py with that bundle path and the corresponding slot. The script refuses pre-existing project resources, creates fresh private local credentials, uses a single Compose without builds, verifies all image identities, seeds only the synthetic fixtures, runs the blocked orchestration boundary and GAMMA/HITL checks, verifies the exact PostgreSQL delta, records elapsed time, and removes only its disposable project volumes. The clock includes pull, startup, seeding and runtime checks on a prepared runner, not provisioning Docker or publishing images.

A passing report is evidence for one fresh application/storage installation. Three passes on one prepared daemon are not three independent host or cold-cache installs. The kit does not yet include the E17 target, a distinct HITL image, a running distributed collector, real LLM/tenant ACL qualification, backup/restore or upgrade/rollback. The product Compose contract is unchanged. File hashes detect inconsistency, not malicious replacement of the bundle or registry trust.
