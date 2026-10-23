# STAR V2.13.33 — Prévisualisation statique HTML + JSON

Le nouvel export `demo/star_portal_export.py` assemble **une seule fois** les preuves contrôlées et leur représentation STAR, puis écrit deux livrables cohérents : `storyboard.json` et `storyboard.html`. Le rendu HTML utilise les neuf jalons canoniques et montre sans ambiguïté toute capture absente ou simulée.

## Essai sur un scénario sans capture

```bash
mkdir -p /tmp/star-acme-test
printf '%s\n' '{"run_id":"STAR-ACME-001","captures":{}}' > /tmp/star-acme-test/manifest.json
python3 -m demo.star_portal_export /tmp/star-acme-test/manifest.json --root /tmp/star-acme-test --scenario SAN_FABRIC_P1 --out /tmp/star-acme-test/preview
# ouvrir localement /tmp/star-acme-test/preview/storyboard.html
```

Le scénario ci-dessus est **fictif et sans capture**, pas une preuve applicative. Aucune requête HTTP ou écriture distante n'est exécutée. Les fichiers sont créés exclusivement (aucun écrasement, permissions 0600), et les sorties partielles sont nettoyées en cas d'échec.

## Qualification

`python3 -m unittest discover -s tests -p 'test_star_portal_export.py' -v`

L'ajout est relié au workflow `star-capture-evidence.yml`. Ne pas qualifier les tests du nouveau commit tant que GitHub Actions n'a pas publié le résultat. En particulier, la CI globale AIOps a déjà connu des échecs Temporal E2E indépendamment de STAR.

## Limites exactes

Cet export est un **preview local**, pas un nouveau portail et **pas encore monté** sur le portail V1 :17777. Pas de navigation Chromium, pas de véritable capture de session, pas d'attestation d'état n8n/GLPI/Grafana, pas d'approbation HITL ni remédiation LIVE.

Prochain jalon : inspection du code déployé pour raccorder la route de consultation au portail unique, lecture seule ; qualification navigateur de l'authentification et des pages cibles à partir de données synthétiques isolées, sans redémarrer la production.
