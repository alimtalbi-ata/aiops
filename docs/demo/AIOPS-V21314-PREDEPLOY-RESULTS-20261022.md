# AIOps V2.13.14 — Préqualification avant déploiement (22 octobre 2026)

Résultats transmis par l'opérateur sur SRV-DEB-05.

- Chromium V2.13.14, frise synthétique (exécution précédente) : 11/11 PASS.
- Régression V2.13.13 sur HTML V2.13.14 : 15/15 PASS, erreurs JS [].
- Régression V2.13.12 sur HTML V2.13.14 : 13/13 PASS, erreurs JS [].
- Docker rootless : construction `aiops2-portal:v21314` réussie, manifest list `sha256:f812e8c35f8c46c28d7786735c9eb6ff8ced0001cd0d7014f738b2c79805f486`.
- Import FastAPI dans `docker run --rm --network none` : routes /, /demo/, /demo/star, /demo-studio; asset inclut V2.13.14, storyline-track, SIMULATED_TARGET.
- `AIOPS_V21314_IMAGE=PASS`.

L'image est candidate, **pas encore déployée** sur 17777 d'après ces logs. La dernière version déployée confirmée est V2.13.13. Test de sécurité et de navigateur sur URL réelle V2.13.14 encore requis; pas de preuve DGX/Core/Policy LIVE.
