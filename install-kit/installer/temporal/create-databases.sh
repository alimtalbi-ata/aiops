#!/usr/bin/env bash
set -euo pipefail

# CANDIDAT PRIVE - NE PAS EXECUTER SUR LE SERVEUR ACTUEL
# Destine exclusivement a l'installation neuve AIOPS2.

: "${TEMPORAL_DB_HOST:?requis}"
: "${TEMPORAL_DB_USER:?requis}"
: "${TEMPORAL_DB_PASSWORD:?requis}"
: "${TEMPORAL_DB_NAME:?requis}"

if [[ "$TEMPORAL_DB_HOST" != "temporal-postgres" ]]; then
    echo "ERREUR : hote PostgreSQL Temporal non autorise" >&2
    exit 1
fi

if [[ "$TEMPORAL_DB_NAME" != "temporal" ]]; then
    echo "ERREUR : nom de base Temporal inattendu" >&2
    exit 1
fi

export PGPASSWORD="$TEMPORAL_DB_PASSWORD"

# Verifier la connexion AVANT toute operation.
psql -X -v ON_ERROR_STOP=1 \
    -h "$TEMPORAL_DB_HOST" \
    -U "$TEMPORAL_DB_USER" \
    -d postgres \
    -tAc "SELECT 1" | grep -qx 1

for database in temporal temporal_visibility; do
    if ! result="$(psql -X -v ON_ERROR_STOP=1 \
        -h "$TEMPORAL_DB_HOST" \
        -U "$TEMPORAL_DB_USER" \
        -d postgres \
        -tAc "SELECT 1 FROM pg_database WHERE datname = '$database'")"; then
        echo "ERREUR : verification PostgreSQL echouee" >&2
        exit 1
    fi

    if [[ "$result" == "1" ]]; then
        echo "Base deja presente : $database"
    elif [[ -z "$result" ]]; then
        createdb \
            -h "$TEMPORAL_DB_HOST" \
            -U "$TEMPORAL_DB_USER" \
            "$database"
        echo "Base creee : $database"
    else
        echo "ERREUR : reponse PostgreSQL inattendue" >&2
        exit 1
    fi
done

echo "OK | Bases Temporal presentes"
