# AIOPS2 — Temporal 1.31.0
# Construction candidate, non qualifiee pour la production.
FROM temporalio/admin-tools:1.31.0 AS admin

FROM temporalio/server:1.31.0

COPY --from=admin /usr/local/bin/temporal-sql-tool /usr/local/bin/temporal-sql-tool
COPY --from=admin /usr/local/bin/temporal /usr/local/bin/temporal

COPY setup-postgres.sh /opt/aiops2/temporal/setup-postgres.sh

# Le CMD officiel de temporalio/server est conserve.
# Integration du schema au demarrage : A REALISER.
# Validation des dependances binaires : A REALISER.
# Validation sur base vierge et base existante : A REALISER.
