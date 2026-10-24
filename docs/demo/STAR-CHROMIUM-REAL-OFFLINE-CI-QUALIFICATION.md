# STAR — Qualification Chromium réelle en environnement isolé

## Objectif
Après l'implémentation de `demo/star_offline_chromium_fixture.py`, le dépôt dispose d'un nouveau test d'intégration `tests/test_star_offline_chromium_render.py` et d'une GitHub Action dédiée `star-offline-chromium-real-render.yml` qui **lance réellement Chromium**.

## Cinématique exécutée dans la CI
1. Installation de Python Playwright et de Chromium dans le runner GitHub Actions.
2. Génération d'un fichier HTML **synthétique local** comportant le marquage « TEST FIXTURE ».
3. Ouverture de ce contenu par Playwright, dans un contexte sans téléchargements ni service workers et avec toutes les requêtes réseau interceptées et bloquées.
4. Production d'un PNG, calcul du SHA-256 et validation de la structure PNG/CRC par `demo.star_png_integrity.inspect_png`.
5. Vérification du manifeste : `origin=SYNTHETIC_LOCAL_FIXTURE`, `runtime_authenticated=false`, `runtime_proof_count=0`, `live_action_authorized=false`.

## Interprétation
Le test **ne constitue pas** une capture métier GLPI, n8n ou Grafana. Il vérifie seulement, sous réserve de réussite de la CI, qu'un navigateur réel peut créer une image de fixture valide et un manifeste cohérent. Aucun port sur Debian n'est exposé, aucun jeton ou état de connexion n'est utilisé et aucune remédiation LIVE n'est déclenchée.

## Prochaine étape
Étendre ce test avec neuf pages de démonstration locales et le rejeu des échecs d'identité. La qualification du vrai portail `:17777` doit être effectuée séparément, avec des accès autorisés, des écrans métier réellement authentifiés et une preuve d'identité par événement.

**Statut :** code et workflow publiés ; consulter GitHub Actions au commit final avant d'annoncer un succès réel de Chromium.
