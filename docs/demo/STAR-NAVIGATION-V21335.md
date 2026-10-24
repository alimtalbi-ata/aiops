# STAR V2.13.35 — Navigation accessible par scène

## Nouvel élément implémenté
`demo.star_navigable_preview.render_navigator(transport, scenario)` crée une page HTML locale parcourable avec **9 ancres** et une section par étape de la cinématique SAN Fabric P1 ou Payments P2. Le scénario, l'ordre des étapes, l'application attendue et la provenance sont validés par `demo.star_scene_scripts.scene_plan`.

La page ne contient ni JavaScript, ni iframe, ni formulaire, ni image distante ni liens vers les instances de production. Elle est compatible navigation clavier et affiche l'absence de preuve ou le caractère fictif d'une illustration. Les métadonnées non prévues du JSON ne sont jamais intégrées au HTML.

## Qualification
```bash
python3 -m unittest discover -s tests -p 'test_star_navigable_preview.py' -v
```
Tests ajoutés à `.github/workflows/star-capture-evidence.yml`. Résultat à examiner sur le dernier commit de PR #36, sans assimiler la présence des tests à un PASS.

## Limites
Cette sortie est **autonome et hors ligne** et ne représente pas encore une route du portail déployé sur le port 17777. Les scènes et captures ne sont pas reliées à une session Chromium authentifiée. La page n'a aucune autorité pour une décision HITL ou une exécution LIVE. Intégration au portail : inspection préalable des sources FastAPI effectivement déployées et validation explicite de la compatibilité.

## Rollback
Revert des fichiers `demo/star_navigable_preview.py`, `tests/test_star_navigable_preview.py` et de la mise à jour CI sur la branche de PR ; pas de changement Debian.
