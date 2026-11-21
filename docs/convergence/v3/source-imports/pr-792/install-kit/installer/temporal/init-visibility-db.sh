#!/usr/bin/env bash
set -euo pipefail

# Installation neuve uniquement.
# Execute par l'entrypoint officiel PostgreSQL
# lorsque PGDATA est initialement vide.

: "${POSTGRES_USER:?POSTGRES_USER requis}"
: "${POSTGRES_DB:?POSTGRES_DB requis}"

if [[ "$POSTGRES_DB" != "temporal" ]]; then
    echo "ERREUR : base principale Temporal inattendue" >&2
    exit 1
fi

# psql est fourni par l'image PostgreSQL.
# Connexion locale pendant l'initialisation.
psql -X -v ON_ERROR_STOP=1 \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    -c 'CREATE DATABASE temporal_visibility;'

echo "OK | Base temporal_visibility initialisee"
