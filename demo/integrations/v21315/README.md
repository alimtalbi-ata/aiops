# ACME V2.13.15 — Kit d'intégration de démonstration (préparation, NON déployé)

## Résultats attendus
- **GLPI** : six CIs fictifs avec dépendances (paiement → VM → ESXi/volume → deux fabrics). Le JSON est un modèle canonique : **pas un export importable GLPI natif**. Mapping vers les catégories/classes GLPI 11, plugins éventuels et schéma REST à confirmer après inventaire de l'instance.
- **Incidents** : deux incidents fictifs non exécutables liés aux CIs, sans ouverture de ticket réelle tant qu'un opérateur n'a pas approuvé l'import dans une organisation DEMO isolée.
- **Grafana** : JSON dashboard importable, utilisant un placeholder `DS_PROMETHEUS`. La seule courbe Prometheus porte sur `up` (présence des scrape targets), **pas sur l'état réel d'un SAN**. Le récit et les incidents sont explicitement synthétiques.
- **n8n** : workflow JSON à importer **inactif**; webhook -> filtre strict `SIMULATED_TARGET` -> réponse DRY_RUN. Aucun connecteur GLPI/Grafana/notification/Worker ni appel de remédiation. L'activation et l'exposition webhook demandent un contrôle de sécurité et une approbation distincte.

## Utilisation immédiate sans risque
`python3 demo/integrations/v21315/validate_fixture.py` (Python standard).

Depuis le correctif de packaging du 26 octobre, ce CLI est un wrapper de compatibilité qui réutilise `app/portal/acme_fixture_contract.py`. Le portail lit la copie identique du fixture `app/portal/acme-fixtures.json`, nécessaire parce que l'image est construite depuis `app/` et ne copie pas le répertoire racine `demo/`. `tests/test_acme_fixture_validation.py` compare les octets des deux fixtures et les résultats du validateur partagé. La CI construit aussi l'image du portail puis exécute uniquement le read model Python dans un conteneur sans publication de port ni démarrage du serveur ; cela vérifie le packaging, pas les intégrations runtime.
Inspecter les fichiers avant tout import; ne jamais exécuter d'automatisation sur production sans séparation des flux, credentials et données.

## Séquence d'implémentation sur Debian (à planifier)
1. Inventaire **lecture seule** GLPI 11, Grafana 13, n8n 2.40.6 : versions, endpoints internes, objets existants, droits; ne publier aucune clé.
2. Créer un périmètre / entité ACME-DEMO avec approbation explicite, mappings CI vérifiés, import idempotent, dry-run/diff, rollback et préfixes de noms stricts.
3. Charger et désactiver par défaut le workflow n8n, valider chaque gate sans side effects, puis n'activer qu'en environnement isolé après approbation.
4. Importer le dashboard Grafana via UI/API après résolution du datasource; vérifier les panneaux, labels, et conserver les preuves de leur provenance.
5. Seule une campagne E2E attestée permet d'annoncer un parcours intégré; distinguer démo fictive, données d'observabilité réelles et inférence DGX.

## Garanties
Pas de second portail utilisateur; UI unique `17777`. Pas de modification Core, Policy, secrets, containers ou bases depuis ces fichiers. Aucun ticket ou incident généré en production par ce commit. 


## Contrat du graphe synthétique

Le validateur contrôle désormais le DAG de dépendances et le chemin d'impact transitif SAN P1 → Payments P2, rejette les actions hors allowlist et reste fail-closed sous `python -O`. Voir `docs/demo/AIOPS-V21315-FIXTURE-GRAPH-VALIDATION-20261026.md` et les tests `tests/test_acme_fixture_validation.py`. Ces contrôles sont hors ligne et ne qualifient pas les connexions runtime.
