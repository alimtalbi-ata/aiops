# STAR — Plan de restauration des captures métier depuis les archives F20.13

## Contexte et objectif
Les échanges d'octobre contiennent des manifestes Playwright UCP/F20.13 et multistack. Une capture PNG dont les octets correspondent à un ancien SHA-256 ne démontre ni l'authentification actuelle, ni que Grafana affiche une alerte, que n8n présente une exécution donnée, ou que GLPI affiche le ticket de ce run. La restauration doit guider une **vraie campagne de captures**, sans confondre preuve historique et preuve métier.

## Modules et contrat
- `demo/star_legacy_capture_gap_plan.py` transforme la sortie expurgée de `demo.star_legacy_playwright_audit` ou `demo.star_legacy_png_verify` en **plan de neuf captures**.
- Les neuf étapes proviennent de `demo.star_snapshot_choreography.CUES` : `detect`, `correlate`, `enrich`, `analyze`, `ticket`, `approve`, `simulate`, `verify`, `close`.
- Pour chaque étape : application, vue et état attendus, nombre d'anciens PNG correspondant aux octets par application, capture métier manquante, prochaine action.
- **Aucun PASS hérité n'est promu au statut runtime.** `runtime_evidence_status=MISSING` demeure pour tous les cues jusqu'à une qualification Chromium distincte.
- Le module n'effectue aucun accès réseau, n'exécute aucune remédiation et n'ouvre aucun port.

## Utilisation hors ligne
```bash
python3 -m demo.star_legacy_png_verify /path/PLAYWRIGHT-EVIDENCE-MANIFEST.json --root /path/evidence-playwright --output /tmp/legacy-verified.json
python3 -m demo.star_legacy_capture_gap_plan /tmp/legacy-verified.json --run-id RUN-TEST-123 --output /tmp/star-capture-gap-plan.json
```

Le second rapport refuse l'écrasement et n'expose aucune URL historique. L'identité du run est un identifiant fourni par l'opérateur : elle n'atteste pas l'existence du run dans la production.

## Qualification et prochaines actions
`tests/test_star_legacy_capture_gap_plan.py` teste les neuf étapes, l'absence de promotion en preuve runtime, le rejet des entrées et run_id invalides et la commande de sortie exclusive. Le workflow STAR capture evidence a été mis à jour pour lancer ces tests. Inspecter la CI du SHA précis avant de qualifier le changement.

La prochaine intégration doit exécuter un navigateur Chromium autorisé, en lecture seule et isolé, vérifiant pour chaque cue l'URL métier, l'authentification, l'identité run_id/incident_id/execution_id/ticket_id et la concordance temporelle avant tout affichage dans le portail :17777. Les captures historiques restent archives documentaires.
