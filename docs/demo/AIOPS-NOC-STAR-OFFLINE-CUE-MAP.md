# NOC — Correspondance illustrative entre captures Chromium et étapes STAR

`demo/noc_star_cue_map.py` classe les trois captures NOC hors ligne en références **illustratives** pour les neuf étapes STAR (`detect`, `correlate`, `enrich`, `analyze`, `ticket`, `approve`, `simulate`, `verify`, `close`). Les noms de captures sont limités à `unified.png`, `synthetic.png`, `checkmk-export.png`. La correspondance ne prétend pas couvrir les neuf étapes par une capture dédiée.

Les captures unifiées illustrent la détection, la corrélation et la vérification ; le panneau ACME synthétique illustre l'enrichissement, l'analyse et la simulation ; l'export Checkmk non authentifié illustre la détection et la vérification. Il ne s'agit PAS d'une association événement→capture vérifiée. Le manifeste de correspondance porte `relationship=ILLUSTRATIVE_ONLY`, `event_bound=false`, `verified_event_links=0`, `run_id=null`, `incident_id=null`, `runtime_authenticated=false`.

Le workflow Chromium crée `star-cue-map.json` dans l'artefact temporaire NOC après validation de l'index des captures et exécute trois tests de régression. Les documents et les tests restent strictement hors ligne. La CI du commit de livraison doit être confirmée avant de considérer l'artefact construit.

**Suite :** une future association vérifiée aux événements STAR devra intégrer des identifiants de run/incident et un lien d'intégrité cryptographique entre événement, instant de capture et artefact. Les neuf étapes ne devront jamais être présentées comme ayant des preuves runtime sur la seule base de ces correspondances illustratives.
