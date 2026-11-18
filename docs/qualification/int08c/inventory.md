# Inventaire exact des références source
Toutes les lignes: SHA SOURCE 13aabde7f05632a36679b96e11334add406d62ac; SHA EXECUTE UNKNOWN; digest image UNKNOWN; qualification runtime NOT_TESTED. Les versions app sont métadonnées FastAPI, non versions d'image. Dockerfiles app basés sur python:3.13-slim non pin; requirements directes fastapi 0.116.1, uvicorn 0.35.0, psycopg 3.2.9, requests 2.32.4, temporalio 1.17.0, pydantic 2.11.7, PyJWT 2.10.1. Transitifs non verrouillés.
| Composant | Version/ref et provenance | Configuration/dépendances | Port interne | Volume proposé |
|---|---|---|---|---|
| Core | 2.0.0 app/core/Dockerfile | DATABASE_URL, POLICY_URL, WORKER_URL, tokens sandbox |810| aucun propre |
| Twin |2.0.0 app/twin/Dockerfile| DATABASE_URL, token sandbox |811| aucun propre |
| Policy |2.1.0 app/policy/Dockerfile| stateless, check POST existant, readback à concevoir |813| aucun |
| Temporal | temporalio/auto-setup:1.32.1 (tag compose)| DB=postgresql, DB_PORT=5432, POSTGRES_SEEDS, POSTGRES_USER/PWD|7233| PG séparé |
| Worker |2.1.0 app/worker/Dockerfile| CORE/EVIDENCE/POLICY/TWIN_URL, token, TEMPORAL_ADDRESS, namespace; flag 0|815| aucun |
| PG app |postgres:16-alpine (tag)| DB/user/password dédiés, init approuvée uniquement|5432|app-data |
| PG Temporal |postgres:16-alpine (tag)| distinct DB/user/password, temporal et visibility à vérifier|5432|temporal-data |
| Collecteur | app/worker/int07_offline_collector.py, pas de version/image autonome | importe portal B et worker C; lecteurs injectés uniquement| aucun| export scellé |
| Portal |2.0.0 app/portal/Dockerfile| additional_context noc_scripts, Core/Twin/Copilot, tokens lecture, liens externes vides|777| aucun |
| Evidence |2.0.0 app/evidence/Dockerfile| DATABASE_URL|812| aucun |
| Copilot |2.0.0 app/copilot/Dockerfile| Core/Twin/Evidence, token|814| aucun |
| Injecteur futur | absent comme client qualifié; simulator 2.0.0 app/simulator/Dockerfile non retenu | une soumission Core autorisée ultérieurement| aucun| aucun |
## Qualification images
Sur builder séparé autorisé: verrouiller base manifest plateforme linux/amd64 (hypothèse), transitifs hashes, build exact SHA, SBOM, scanner, provenance signée, archive offline SHA256. Pour chaque image consigner index digest, manifest plateforme digest, config ID, architecture, source SHA, builder et signature; images tierces version/provenance vendor, pas de faux SHA application. Comparer archives et inspect image/container IDs sur VM via observateur indépendant; aucune pull/build au runtime. Digest tag inconnu = NO-GO. Worker Dockerfile copie shared/worker seulement: collector imports portal absents; proposer image collecteur dédiée avec shared/worker/portal et entrypoint read-only après arbitrage, pas de Dockerfile modifié. Portal build nécessite scripts. Aucun digest récupéré ni image construite.
