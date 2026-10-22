# V2.13.10 — Qualification navigateur et déploiement (22 octobre 2026)

Source: résultats de commandes exécutées par l'opérateur sur SRV-DEB-05. Les rapports JSON/PNG sont présents sur le serveur, non joints au dépôt.

## Contrôle conteneur
- Compose ID: `4b2c01e4fd5a8e6582b0acbc6a2f32c9c9328af1a2d35241681121d40d559b0c`
- ACTIVE_IMAGE = TARGET_IMAGE = `sha256:3405a8b2317816e3681f26848b31f27386126e7c2c81a994cd5e5a187dac5fe4`
- `AIOPS_V21310_POST_DEPLOY=PASS`
- HTTP: `/health` 200, `/` 200, `/demo-studio` 200, `/demo/` 200, `/demo/star` 200, `/demo/view/AIOPS-REAL-STACK-REPLAY.html` 403.

## Chromium réel
`/home/aiops/aiops-v21310-qualification/v21310-browser-report.json` et `v21310-browser-report.png`

Tous les 7 checks PASS : catalogue HTTP, lien STAR, page STAR HTTP, contenu visible, commandes détectées, historique refusé, zéro erreur JS observée. Boutons trouvés : Précédent, Pause, Suivant, Recommencer, 01..12.

Limites : le smoke test **ne vérifie pas** encore l'effet des boutons play/pause, le changement de séquence, le plein écran, les permissions globales ni une remédiation LIVE. Le replay Core reste verrouillé.

## À faire
- Conserver un portail sur 17777.
- Ajouter des tests navigateur d'interaction par bouton et accessibilité.
- Réconcilier les sources exactes déployées de V2.13.10 avec la PR, sans écraser les fichiers Compose locaux.
- Qualifier une procédure de rollback basée sur `docker compose ps -q`.
- Préserver la séparation simulation fictive / historique export opérateur / preuves DGX non attestées.
