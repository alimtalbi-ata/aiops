# AIOps — continuité V2.13.10 (2026-10-22)

## Référence et état observé
Dépôt `alimtalbi-ata/aiops` ; branche dédiée `feat/v21310-star-portal-continuity-20261022`. Portail unique `http://10.79.94.202:17777/`, service Compose `aiops2-portal`, conteneur `aiops2-rebuild-portal` sur Docker rootless.

L'opérateur a confirmé:
- V2.13.9.3 déployée sur le port 17777, image `aiops2-portal:v21391`, avec `/health=200`, `/=200`, `/demo/=403`; replay historique désactivé.
- Sources V2.13.10 créées à `/home/aiops/aiops-portal-v21310-source`.
- Image `aiops2-portal:v21310` construite; test d'import FastAPI `AIOPS_V21310_IMPORT=PASS`. **Non encore déployée**.
- Aucun second portail ne doit être publié; ne pas activer le lancement `/api/demo`.

## Sécurité
Le portail existant présente des routes accessibles anonymement en HTTP. Ne pas transmettre d'identifiants HTTP Basic sur cette connexion. Les replays historiques restent protégés par le module `demo_center_v2139`, désactivés par défaut. La page `/demo/star` est un scénario entièrement fictif et ne doit jamais intégrer données historiques ni secrets.

## Mise en œuvre
1. Réconcilier ce commit avec les sources réellement déployées sur Debian; ne pas écraser les changements locaux ni les fichiers Compose additionnels.
2. Conserver `app/portal/demo_center_v2139.py` et ses contrôles d'accès.
3. Remplacer seulement la route catalogue protégée `/demo/` par `/demo/operator`, afin de permettre le catalogue fictif `/demo/`.
4. Ajouter `from portal import portal_demo_public_v21310` et `app.include_router(portal_demo_public_v21310.router)` dans `portal/main.py`.
5. Fournir l'asset HTML fictif qualifié sous `portal/public_demo_assets/AIOPS-EXECUTIVE-THEATER-PUBLIC.html` depuis le kit opérateur V2.13.10 (ne pas utiliser l'export historique). Contrôler sa provenance et son SHA-256.
6. Construire l'image dédiée; qualifier imports/routes puis parcours STAR en navigateur; sauvegarder l'image actuellement déployée; ne recréer que le service portail.
7. Vérifier `/health=200`, `/=200`, `/demo/=200`, `/demo/star=200`, historiques toujours verrouillés, puis tester le rollback.

## Données probantes et limites
`AIOPS_V21310_IMPORT=PASS` est une qualification de chargement FastAPI, **pas** une qualification navigateur ou une mise en production. Aucun effet LIVE, aucune inférence DGX nouvellement attestée.
