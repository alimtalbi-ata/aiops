# Security and operations

- API binds to loopback by default; use SSH tunnelling for remote access.
- PostgreSQL is not published on the host.
- The Compose network is internal; containers are non-privileged.
- API runs non-root, with read-only root filesystem, dropped capabilities and bounded tmpfs.
- `.env` is generated locally with mode 0600; never upload it or paste it into chat.
- Health endpoints expose no environment values.
- Incident payloads may be operationally sensitive; define retention and access controls before production.
- Automatic remediation is absent and explicitly disabled.
- Backups contain `.env`; keep archives private and rotate credentials if exposed.
