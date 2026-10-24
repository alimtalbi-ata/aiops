# STAR V2.13.36 — Export navigable opérationnel hors ligne

## Livrable fonctionnel

`demo/star_navigable_export.py` raccorde la validation du manifeste au rendu HTML interactif par ancres locales. Il produit simultanément `star-scenes.json` et `star-scenes.html`, utilisables pour préparer la démonstration SAN P1 ou Payments P2 sans exposer de service supplémentaire.

## Exemple reproductible (aucune capture, aucune connexion externe)
```bash
mkdir -p /tmp/star-v21336
printf '%s\n' '{"run_id":"STAR-ACME-001","captures":{}}' > /tmp/star-v21336/manifest.json
python3 -m demo.star_navigable_export /tmp/star-v21336/manifest.json --root /tmp/star-v21336 --scenario SAN_FABRIC_P1 --out /tmp/star-v21336/result
# Consulter localement /tmp/star-v21336/result/star-scenes.html
```

Le rendu présente **neuf scènes** et affiche « Capture absente » partout tant qu'aucun PNG réellement contrôlé n'est fourni. Les éléments ne doivent pas être décrits comme issus de Grafana/GLPI/n8n réels sans preuves supplémentaires. Aucun JavaScript, POST, webhook, API, redémarrage ou déploiement sur le portail 17777 n'intervient.

## Sécurité et qualification

- Manifeste contrôlé avant écriture; scénario et identité cohérents.
- Dossier de sortie non symbolique; création exclusive des fichiers (0600), refus d'écrasement et nettoyage des sorties créées si erreur.
- Tests de scénarios, neuf ancres, refus des symlinks et d'identité invalide dans `tests/test_star_navigable_export.py`.
- Tests raccordés à `.github/workflows/star-capture-evidence.yml`. Leur réussite sur le nouveau SHA reste à observer.
- Une archive contenant des captures authentiques demeure privée et ne doit pas être poussée dans GitHub.

**Limite :** l'export est réellement exécutable sur un checkout ; il n'est pas une route FastAPI ni une intégration déployée. Les captures Chromium synchronisées sur de vraies pages et le raccordement au portail unique 17777 nécessitent encore qualification.

## Suite prioritaire
Inspection des sources du portail réellement en service, adaptateur lecture seule pour la navigation STAR, tests E2E Chromium dans un environnement isolé, preuve d'identité de run entre n8n/Grafana/GLPI. Aucune remédiation LIVE.
