# AIOps2 — Loki / Tempo / OTel : candidat isolé

Statut: **NOT TESTED ON DEBIAN / NO-GO production**. Préparé pour revue dans issue #186. Les versions d'images, les schémas YAML et la compatibilité effective doivent être validés sur la machine avant usage.

## But
Ajouter logs et traces comme preuves du Studio Démo sans toucher aux services AIOps2 existants. Un seul portail AIOps2 reste le point d'entrée. Grafana est une console existante, non remplacée.

## Préconditions
- Docker rootless et réseau externe `aiops2-rebuild-observability` existant.
- Capacité mémoire/disque suffisante (limites cumulées 1920 MiB hors autres services).
- Examiner la confidentialité des logs: ne pas collecter de secrets ni données clients; accès au réseau observability réservé aux composants autorisés.
- Réviser les tags, schémas et droits d'écriture des volumes; versions non vérifiées dans le runtime Debian.
- Aucune instrumentation des applications existantes incluse; sans émetteurs OTLP il n'y aura pas de traces/logs collectés.

## Recette avant lancement
Depuis ce répertoire, après revue:
```sh
docker compose -p aiops2-demo-observability -f compose.yml config -q
docker image inspect grafana/loki:3.5.0 grafana/tempo:2.7.2 otel/opentelemetry-collector-contrib:0.123.0 >/dev/null
```
Si les images sont absentes, valider leurs versions et les récupérer volontairement; ne pas lancer de déploiement implicite.

## Lancement contrôlé (opérateur uniquement, APRÈS validation)
```sh
docker compose -p aiops2-demo-observability -f compose.yml up -d --no-build
docker compose -p aiops2-demo-observability -f compose.yml ps
docker compose -p aiops2-demo-observability -f compose.yml logs --tail=40
```
Ne jamais coller des logs contenant des tokens ou données sensibles dans une issue publique.

## Validation
- Conteneurs running, aucun redémarrage en boucle.
- Tester `/ready` Loki, `/ready` Tempo, API du collector depuis le réseau Docker (sans publier de ports).
- Ajouter dans Grafana des datasources Loki (`http://demo-loki:3100`) et Tempo (`http://demo-tempo:3200`) après vérification réseau, droits et authentification.
- Injecter uniquement une trace/log synthétique explicitement étiquetée DEMO, confirmer présence et horodatage; collecter l'ID réel pour Evidence.
- Documenter tests, SHAs, captures réelles, limites et rollback. Ne pas annoncer un E2E avant instrumentation.

## Rollback
`docker compose -p aiops2-demo-observability -f compose.yml down` arrête uniquement les 3 conteneurs de ce projet; les volumes nommés restent conservés (NE PAS ajouter `-v`). Ne pas exécuter de rollback sans raison.

## Checkmk et Thruk
Hors de cette première livraison: à cadrer séparément (licence/édition, ressources, image de confiance, données persistantes, réseau, API, authentification, éventuelle redondance fonctionnelle) avant déploiement.

## Sécurité
Loki et Tempo n'apportent pas ici de couche d'authentification applicative. Ne jamais publier leurs ports sur le LAN. Le collector OTLP n'est accessible qu'aux membres du réseau Docker observability. Aucun changement de production, de cron, de stable ou de secrets.
