# AIOps V2.13.12 — Mode présentateur et lecture chronométrée

## Objectif utilisateur
Un message central par scène et une preuve explicite en lecture secondaire. L'expérience doit convaincre un comité sans encombrer le support.

## Changements livrés sur la branche
- Mode présentateur : masque les notes à droite et agrandit le message central; le bouton redevient « Afficher les notes » pour revenir.
- État de lecture explicite : « Lecture arrêtée » ou « Défilement automatique · 5/8/12 s ».
- Timer contrôlé : timer annulé à la pause, au redémarrage et à la fin; changement de vitesse réinitialise le délai actif; arrêt à la douzième scène.
- 12 scènes conservées, sans ajout de nouvelle API ou collecte d'historique.
- Provenance `SIMULATED_TARGET` et avertissements sur l'absence d'effet LIVE conservés.

## Qualification requise
1. Sur Debian, extraire le HTML de cette branche via `git show FETCH_HEAD:app/portal/public_demo_assets/AIOPS-EXECUTIVE-THEATER-PUBLIC.html` dans une copie de l'arborescence, jamais directement dans le conteneur actif.
2. Extraire `tests/browser/qualify_v21312_star.py`.
3. Tester en `file://` dans Chromium avec Playwright: présentateur aller/retour, lecture auto à 5 s, pause bloquée pendant 5,5 s, mobile sans débordement, aucune erreur JS.
4. Comparer avec la qualification V2.13.11, construire l'image candidate `aiops2-portal:v21312` sans la déployer, puis faire contrôle d'import et routage.
5. Déployer uniquement le service portail après PASS, contrôle rollback, et revérifier HTTP 403 pour les fichiers historiques. Rejouer ensuite Chromium sur `http://10.79.94.202:17777/demo/star`.

## Limitations
Les changements sont publiés sur GitHub mais le test Chromium V2.13.12 n'a pas encore été exécuté sur Debian. Aucun déploiement V2.13.12, aucun appel DGX ni changement à la Policy n'est revendiqué.

## Sécurité et architecture
Port utilisateur unique : 17777. Aucun autre portail ni port. La démo est purement synthétique, les replays historiques et la remédiation LIVE restent verrouillés. Pas de fusion automatique de la PR #36, ne pas publier de secrets, préserver Compose locaux.

## Continuité de version
Base déployée vérifiée : V2.13.11, commit de code V2.13.12 dans PR #36. Conserver la procédure de sauvegarde/restauration d'image, éviter `docker inspect` sur un nom de conteneur figé : préférer `docker compose ps -q aiops2-portal`.
