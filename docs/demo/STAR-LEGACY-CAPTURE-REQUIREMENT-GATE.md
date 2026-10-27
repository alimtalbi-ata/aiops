# STAR — Validation des lacunes historiques avant la campagne Chromium

## But
Le module `demo/star_capture_execution_worklist.py` combine le plan d'identité d'un run et l'état des captures F20.13. Une ancienne métadonnée doit rester descriptive : elle ne doit pas supprimer une étape, déplacer son état métier ou forger un nombre de PNG réutilisables.

## Contrôles ajoutés
- `expected_state` de chaque scène doit correspondre à `CUES.required_state`. Par exemple, une détection Grafana attend `firing`, pas `resolved`.
- `legacy_png_byte_matches_for_application` doit être un entier de 0 à 128. Les booléens, chaînes, valeurs négatives et nombres hors bornes sont refusés.
- `capture_required` doit rester `true` pour les neuf étapes, même lorsque des images historiques ont été vérifiées au niveau des octets.

La sortie est **un plan de travail**, pas une preuve d'exécution : `runtime_proof_count=0`, `live_action_authorized=false`.

## Qualification
Les nouveaux tests de `tests/test_star_capture_execution_worklist.py` simulent les trois classes de corruption. Les tests sont déjà pris en charge par `.github/workflows/star-capture-evidence.yml`. Consulter la CI au SHA précis.

## Prochaine intégration
Faire exécuter ce plan par une campagne Chromium *isolée*, en lecture seule, avec authentification explicite et identité du run vérifiée sur la bonne page métier. Les traces F20.13 seules ne garantissent ni l'écran ni l'heure de capture. Aucune action sur la production Debian.
