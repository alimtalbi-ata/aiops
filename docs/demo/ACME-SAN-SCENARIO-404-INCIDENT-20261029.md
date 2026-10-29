# Incident ACME SAN — diagnostic 404 scénario (2026-10-29)

## Conclusion observée

Run `RUN-073A9D4D7B4B767C`, scénario déclaré `acme-san`. L'événement du run est `DGX_ANALYST / INTELLIGENCE_UNAVAILABLE / BLOCKED`, `payload.reason=HTTPError`, `execution_allowed=false`. Le journal Core dans la fenêtre `2026-10-29T11:46:00Z`–`11:49:00Z` contient :

```text
GET /api/scenarios/acme-san HTTP/1.1" 404 Not Found
```

Aucun `POST /api/intelligence/` n'apparaît dans les journaux filtrés du service Intelligence sur cette fenêtre. Les accès Evidence `GET /api/evidence?run_id=RUN-073A9D4D7B4B767C` et plusieurs `POST /api/evidence` ont répondu 200. Les conteneurs Core, Worker, Intelligence et Policy étaient `running | healthy` lors de l'inspection ultérieure.

## Chemin de code confirmé

Dans `app/worker/main.py`, pour `DGX_ANALYST`, le Worker :
1. lit `/api/runs/{rid}` ;
2. lit `/api/evidence?run_id={rid}` ;
3. lit `/api/scenarios/{scenario}` ;
4. **seulement ensuite** appelle `POST /api/intelligence/analyze`.

Le bloc `except Exception as exc` transforme toute exception de cette séquence en `INTELLIGENCE_UNAVAILABLE`, avec `reason=type(exc).__name__`, `HUMAN_APPROVAL`, `execution_allowed=false`, puis `BLOCK`. Ce libellé est donc trop générique pour distinguer une ressource scénario absente d'une indisponibilité IA.

La réponse 404 de Core pour `acme-san` est la **cause immédiate fortement étayée** du blocage observé. Le mécanisme exact à l'origine du 404 (scénario absent, nom/identifiant divergent, seed manquant, version ou configuration) n'est pas encore établi. Aucun changement de runtime ni remédiation n'a été effectué.

## Vérifications suivantes, en lecture seule

- Examiner les routes et la source des scénarios dans Core, le catalogue/seed de scénarios, et la valeur `scenario_id` effectivement stockée pour le run.
- Comparer les identifiants de scénarios disponibles avec `acme-san`; ne pas créer ou renommer un scénario sans contrat explicite.
- Vérifier si d'autres runs sont concernés; ne pas débloquer rétroactivement ce run.
- Corriger dans une branche dédiée, tester la résolution du scénario, l'absence d'appel Intelligence en cas de 404 et le fail-closed, puis déployer seulement après validation.
- Envisager un événement diagnostique plus précis (`SCENARIO_UNAVAILABLE`) sans réduire les garde-fous. Ce n'est **pas** encore une modification implémentée.

## Problème séparé

Le service Evidence renvoie régulièrement `404` sur `GET /metrics`. Il s'agit d'un défaut potentiel d'exposition ou de configuration de collecte des métriques, **non établi comme cause du blocage Analyst**.

## Impact sur la vidéo

Le run reste `BLOCKED`. Ne pas le présenter comme une démonstration SAN → Payments réussie, ni comme preuve LIVE. Voir [inventaire runtime et vidéo](ACME-RUNTIME-VIDEO-PLATFORM-20261029.md).
