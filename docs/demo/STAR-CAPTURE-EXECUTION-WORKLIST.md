# STAR capture execution worklist — F20.13 × identity plan

## Contexte
Le patrimoine Playwright F20.13 documente des images historiques, tandis que `star_capture_identity_cli.py` établit quels identifiants ont été fournis pour neuf étapes de la cinématique STAR. Pour obtenir une campagne exploitable, `demo/star_capture_execution_worklist.py` joint ces deux **plans hors ligne**, en refusant une discordance de `run_id` ou de séquence de scènes.

## Entrées
- `star-capture-identity-plan-v1` : run et identifiants de preuves par scène.
- `star-legacy-capture-gap-plan-v1` : neuf scènes et nombre de PNG historiques dont les octets correspondent par application.
- Schéma de référence : `demo.star_snapshot_choreography.CUES`.

## Exécution
```bash
python3 -m demo.star_capture_execution_worklist /tmp/star-ready.json /tmp/star-capture-gap-plan.json --output /tmp/star-worklist.json
```

Le JSON est créé exclusivement (sans écrasement), en lecture seule. La sortie classe les scènes en `MISSING_IDENTIFIERS` ou `READY_FOR_READ_ONLY_CAPTURE`. Ce second état **autorise seulement à envisager une capture** après vérification explicite du navigateur et des accès : ce n'est pas une preuve d'exécution réelle. `runtime_proof_count=0` et `live_action_authorized=false` restent imposés. Aucune URL, jeton ou capture sensible n'est embarqué.

## Contrôles et limites
Cinq tests couvrent les identifiants manquants, une préparation partielle, les divergences de run, les affirmations runtime frauduleuses et les scènes désalignées. Le workflow `STAR screenshot integrity collector` a été étendu pour les compiler et les tester.

**Non réalisé** : capture Chromium authentifiée, qualification des véritables vues métier, confirmation de la relation événement/capture, intégration runtime du portail :17777. Aucun redémarrage ni modification de la stack Debian. Inspecter les résultats CI sur le commit précis avant de qualifier cette livraison.
