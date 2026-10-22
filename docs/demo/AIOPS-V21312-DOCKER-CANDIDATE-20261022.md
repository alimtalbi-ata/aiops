# V2.13.12 — Build candidat confirmé (2026-10-22)

Résultat fourni par l'opérateur depuis SRV-DEB-05.

- Image Docker `aiops2-portal:v21312` construite avec succès sous Docker rootless.
- Export manifest list `sha256:a9e764d065085ea18aa4a0521740ff9c0565ea02b1d10b02dc12236ebd0f3126` (sortie de build).
- Le test isolé `docker run --rm --network none --entrypoint python` valide l'import FastAPI, la présence des routes `/`, `/demo/`, `/demo/star`, `/demo-studio`, l'existence du fichier HTML STAR sans symlink et sa version `V2.13.12`.
- `AIOPS_V21312_IMAGE=PASS`.
- Chromium local précédemment qualifié : 13/13 checks PASS.
- **Ce résultat ne constitue pas un déploiement** : la dernière version confirmée sur `17777` reste V2.13.11 avant nouvelle preuve.

Procédure prévue: réutiliser le script V2.13.11 qualifié en versionnant une copie V2.13.12, vérifier rollback et image précédente, recréer uniquement le portail, vérifier HTTP 200 /demo/ et /demo/star ainsi que HTTP 403 sur le replay historique, puis exécuter les 13 tests Chromium directement sur le portail.

Aucun effet LIVE, aucun replay historique autorisé, aucun second portail, aucun merge automatique.
