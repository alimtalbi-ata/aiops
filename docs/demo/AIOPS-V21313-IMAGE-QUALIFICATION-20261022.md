# V2.13.13 — Construction Docker qualifiée (22 octobre 2026)

Compte rendu de la sortie exécutée par l'opérateur sur SRV-DEB-05.

- Image candidate : `aiops2-portal:v21313`.
- Docker rootless `docker build` : réussite.
- Manifest list produit : `sha256:1c0e808b9cad5ad77236269a2310edbc90658c289940cef226c76a4984fbc071`.
- `docker run --rm --network none --entrypoint python` : import `portal.main`, routes `/`, `/demo/`, `/demo/star`, `/demo-studio`, asset existant sans symlink, V2.13.13 / SIMULATED_TARGET / evidence-panel / SVG confirmés.
- `AIOPS_V21313_IMAGE=PASS`.
- Qualification navigateur du HTML local antérieure : 15/15 PASS.
- Non encore validés pour cette candidate : régression du minuteur V2.13.12 sur HTML V2.13.13, HTTP 403 en runtime V2.13.13, navigateur après déploiement, rollback exécuté. Pas de déploiement revendiqué.

Continuité : un seul service portail et port 17777. Ne pas ouvrir les replays historiques ni des actions LIVE. Préserver fichiers Compose non suivis et main.
