# FS.1040 — Local candidate image for SQL guard

Builds `aiops2-portal:fs1040-sql-guard-candidate` FROM the existing `aiops2-portal:fs621-explorers-candidate` image, retaining its routes and code except for a hash-guarded replacement of `_safe_query`. The patch runs **at build time**; no production container is modified and no runtime monkeypatch is needed.

Run `bash scripts/fs/FS.1040-build-and-qualify.sh /path/to/worktree` from the host. The build uses `--network none`. Tests run with `--network none --read-only` and no DB access.

**Security limits:** regex guard is not a SQL parser; read-only DB privileges and transactions must be independently verified. The image is a **local candidate**, not a deployment or proof of database security. Do not run on 7777, tag as production, or replace any running service without explicit approval. The deployed explorer source remains absent from the branch; reconcile it before longer-term maintenance.
