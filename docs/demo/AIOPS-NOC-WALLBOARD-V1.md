# NOC Command Center — dashboard HTML interactif de démonstration

**Statut : interface statique fonctionnelle pour événements SYNTHETIC ; pas d'accès live Checkmk/Thruk/GLPI/n8n/Grafana.**

## Objectif
Établir la première surface NOC réellement consultable à partir du modèle multiconstructeurs déterministe. Le code `demo/noc_wallboard.py` convertit `aiops-noc-synthetic-snapshot-v1` en une page HTML autonome avec :
- compteur des hôtes, services métiers et alertes ;
- inventaire des équipements et états (OK/WARN/CRIT/UNKNOWN) ;
- impact métier ACME Payments, table d'alertes avec identifiants du corpus RAG ;
- filtres interactifs « Tous / Critiques / Avertissements / OK » ;
- indication persistante et visible « DONNÉES SYNTHÉTIQUES DE DÉMONSTRATION ».

## Génération
Depuis la racine du dépôt, exécuter :
```bash
python -m demo.noc_wallboard --output /tmp/aiops-noc-demo.html
```
Ouvrir ce fichier localement dans le navigateur. La génération refuse l'écrasement d'un fichier existant. Le HTML produit n'utilise ni CDN ni API distante ; les étiquettes issues du catalogue passent par l'échappement HTML, et aucune action POST/PUT, acquittement ou remédiation n'est proposée.

## Contrats de sécurité et limites
Le programme refuse toute déclaration `checkmk_live=true`, `thruk_live=true`, `runtime_authenticated=true` ou `live_remediation_authorized=true`. Les états sont dérivés d'une table de scénarios **synthétiques** ; ils ne doivent jamais se substituer à la supervision réelle. Ce dashboard ne prétend pas être installé dans le portail `:17777`.

## Qualification
`tests/test_noc_wallboard.py` vérifie le HTML, le filtrage déclaré, l'échappement d'une valeur hostile, la non-promotion de statuts LIVE, le rejet d'un état inconnu et le refus d'écrasement. Le workflow `aiops-rag-ops-fixtures.yml` a été mis à jour pour l'exécuter. Vérifier la conclusion du nouveau commit.

## Prochain pas
Intégrer le wallboard au portail dans une route DEMO isolée, puis créer un adaptateur de supervision Checkmk/Thruk en lecture seule avec validité temporelle des données, séparation client/DC, preuves d'identité des événements et un lien run_id vers la timeline STAR. Préserver les conteneurs `aiops_noc_checkmk` et `aiops_noc_thruk` historiques jusqu'à l'audit des volumes et configurations.
