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


## Contrat V2 — identité métier complète par checkpoint (27 octobre 2026)

La campagne historique F20.13 ne liait pas de façon fiable une capture à l'incident métier, au ticket GLPI ni à l'heure de l'événement qui est censé être affiché. Le validateur conserve donc le contrat historique star-browser-evidence/v1, et ajoute une version explicite star-browser-evidence/v2 sans promouvoir les anciennes données.

Le contexte canonique V2 attendu par le validateur suit le schéma star-canonical-checkpoint-context/v1 :

- identité indépendante du scénario : run_id, correlation_id, incident_id ;
- map des neuf checkpoints : event_ref, ticket_id et event_timestamp_utc pour chacun ;
- ticket_id: null avant le checkpoint ticket ; à partir de ticket, un identifiant de ticket explicite est obligatoire. Le validateur ne copie jamais un identifiant absent depuis un checkpoint voisin ;
- event_timestamp_utc est soit explicitement null, soit une chaîne UTC canonique terminée par Z. L'heure de capture captured_at reste un champ distinct. La correspondance avec le contexte attendu ne prouve ni l'heure serveur réelle ni l'authenticité de la page ;
- les valeurs du manifeste doivent correspondre exactement au contexte fourni indépendamment. Les identités et l'horodatage font partie de l'empreinte déterministe V2 du jeu complet de captures.

Le manifeste V2 rend obligatoire la présence des trois champs de contexte, y compris lorsqu'une valeur est absente (null). Toute divergence d'incident, de ticket, d'événement ou d'heure, un ticket avancé avant son checkpoint, une heure non canonique, un PNG substitué ou une attestation runtime injectée fait échouer la qualification. Le rapport conserve SIMULATED pour les fixtures HTML locales, runtime_authenticated=false, business_validated=false, human_approval_authenticated=false et live_action_authorized=false.

### Interfaces et qualification

Le module demo/star_browser_manifest_gate.py valide le contexte attendu puis les manifestes/PNG locaux ; tests/test_star_browser_manifest_gate.py couvre neuf cues synthétiques, l'absence explicite d'heure, la transition d'identité GLPI, les divergences et l'invalidation du hash de replay. Le contrat V1 demeure compatible pour les exports historiques qui ne contiennent pas les champs V2.

Aucun accès réseau, navigateur de production ou écriture applicative n'est requis par ces tests. Le workflow de bridge STAR et le kit cumulatif ciblent déjà ce module, cette suite et docs/recovery/** ; leur exécution sur le nouveau SHA reste nécessaire avant de déclarer la CI qualifiée.

### Retour arrière

Revenir ensemble sur le changement du validateur, ses tests V2 et cette section documentaire, sans action de runtime. Ne supprimer ni remplacer les manifestes V1 historiques. L'ajout V2 vérifie seulement la cohérence de données d'entrée locales : il ne remplace pas une capture Chromium authentifiée des neuf écrans, ne qualifie pas le portail Debian :17777 et n'autorise aucun effet LIVE.
