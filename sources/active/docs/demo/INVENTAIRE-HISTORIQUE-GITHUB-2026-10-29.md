# Inventaire transversal GitHub — première passe, 2026-10-29

**Objectif :** réutiliser les deux mois de développement avant d'écrire du code ou de déployer. Cette passe repose sur l'énumération GitHub des branches et sur la lecture de fichiers sélectionnés, **pas** sur un audit exhaustif des commits ni des fichiers locaux non suivis.

## Résultat majeur : simulateur de remédiation EXISTANT
- Branche `feat/p0-hitl-remediation-lab-simulator-20261027-2024`
- Sources effectivement lues : `app/shared/remediation_lab.py`, `config/remediation/recipes.v1.json`, `tests/test_remediation_lab.py`.
- **8 recettes** en `SIMULATOR_ONLY` : inspection Bash Linux, diagnostic Python disque, redémarrage de service Ansible simulé, statut Linux CLI, inspection interface Network CLI, santé DB CLI, acquittement Checkmk API simulé, note GLPI API simulée.
- `validate_proposal` : schéma exact, recettes et cibles autorisées, types stricts, références de secret Vault seulement, empreinte canonique SHA-256.
- `evaluate_simulation` : refuse LIVE, décision non approuvée, empreinte modifiée, approbateur non authentifié, auto-approbation, expiration, préconditions absentes ou fausses ; renvoie `NO_EFFECT_SIMULATOR`, `effect_applied=False`, paramètres secrets masqués, clé d'idempotence déterministe.
- **Limite essentielle** : le résultat est une trace de simulation sans effet ; `postchecks=NOT_RUN`, pas de projection d'état avant/après, pas de vérification postcondition réelle ni d'exécution d'adaptateur. Le champ `authenticated=True` est une **fixture**, pas une authentification d'entreprise. Les 10 méthodes de test sont **présentes**, mais **non exécutées dans cette passe**.
- **Décision** : NE PAS réécrire ce module. Comparer son intégration avec la consolidation P0, tester en isolation, puis ajouter un moteur de projection déterministe avant/après et rollback **sans effet réel**, avec provenance et séparation d'approbation.

## Branches candidates effectivement identifiées
| Fonction | Branche historique | Lecture effectuée / conclusion |
|---|---|---|
| Remédiation simulée et HITL | `feat/p0-hitl-remediation-lab-simulator-20261027-2024` | Module + catalogue + tests lus ; à réutiliser après audit |
| Demo Studio V2 | `release/p0-demo-v2-ui-candidate-20261029-0004` | `app/portal/demo_v2.py` lu partiellement ; affiche sources et erreurs sans inventer d'état |
| Demo Studio antérieur | `feat/demo-studio-v2-delivery-20261028` | Ancien `app/portal/demo_v2.py` lu partiellement ; comparer au candidat plus récent |
| Topologie ACME entreprise | `feat/p0-acme-enterprise-60ci-20261028-1115` | `db/migrations/005_seed_acme.sql` lu partiellement ; nœuds SAN, réseau, paiements et ERP ; compter/qualifier avant d'affirmer 60 CI réels |
| Contrat scénarios | `feat/p0-acme-scenario-contract-20261028-1153` | Branche identifiée, fichiers à lire |
| Corrélation NOC/ITSM | `feat/acme-core-noc-itsm-correlation-20261027` | Branche identifiée, intégration à examiner |
| GLPI | `feat/acme-glpi-internal-reader-20261028-0138`, `feat/p1-glpi-real-http-ci-20261028-1035` | Branches identifiées, qualifier la lecture réelle et les permissions |
| Golden journey | `feat/golden-demo-journey-20261027` | Branche identifiée, à lire |
| Copilot/RAG | `feat/noc-synthetic-rag-drilldown-20261027-2316`, `fix/p0-copilot-grounding-20261027` | Branches identifiées, à lire |
| Observabilité | `feat/observability-loki-tempo-otel-20261029` | Branche identifiée, à lire ; ne pas présumer le déploiement |
| Source actuelle | `feat/p0-runtime-consolidated-20261029` puis `prep/acme-demo-offline-20261029` | P0 consolidé et 26 contrôles statiques Debian PASS |

## Attention aux divergences
Le `app/policy/main.py` lu sur l'ancienne branche remediation est une version antérieure et moins restrictive que le Policy P0 consolidé. **Ne jamais cherry-pick aveuglément l'ensemble de cette branche** : extraire les modules ciblés et les tests, comparer les imports, contrats et gardes, puis faire une intégration isolée. Même règle pour `app/portal/main.py`.

Le `app/portal/demo_v2.py` de la branche candidate de release existe sur GitHub, tandis qu'un `app/portal/demo_v2.py` non suivi avait été signalé dans le worktree Debian historique. Il faut comparer les contenus avant de choisir ; ne pas écraser.

## Suivi et preuves
- Dépôt : `alimtalbi-ata/aiops`.
- Base de travail : `prep/acme-demo-offline-20261029`, Debian au SHA `e1748b7` lors du dernier message opérateur.
- Les recherches de code GitHub sur la branche par défaut peuvent manquer les fonctionnalités en branches non fusionnées. La découverte du simulateur de remédiation a été faite en inspectant **explicitement la branche historique**.
- Aucune commande Docker, aucun test de remédiation, aucun déploiement dans cette passe.

## Actions suivantes, dans l'ordre
1. Comparer les fichiers du labo de remédiation à la branche prep, vérifier qu'aucun composant équivalent plus récent n'existe, puis porter **uniquement** le module/catalogue/tests dans une branche de préparation après vérification de compatibilité.
2. Auditer Demo Studio V2, le contrat scénarios, la topologie ACME, le NOC/GLPI, les intégrations Copilot et l'observabilité ; produire une matrice de fonctions/contrats/tests/risques et éviter les doublons.
3. Qualifier le module de remédiation et ajouter la simulation d'état avant/après et rollback sans effets ; rattacher le résultat au `run_id` et à l'interface.
4. Préparer les tests E2E isolés puis le kit de déploiement ; pas de déploiement des conteneurs existants avant GO explicite.
