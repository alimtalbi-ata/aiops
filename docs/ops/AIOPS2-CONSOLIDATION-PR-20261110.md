# Consolidation des développements AIOPS2 — décision d'intégration

Date : 2026-11-10. **Objet : faire évoluer la plateforme AIOPS2 déjà installée sur Debian**, sans écraser l'installation existante. Cette note est un tri des PR sur GitHub, **pas** une preuve de validation runtime.

## Cartographie vérifiée des PR candidates

| PR | Apport candidat | Branche de base GitHub | Décision provisoire |
| --- | --- | --- | --- |
| #515 | Core : refuser un scénario persistant corrompu avant dispatch Worker | `agent/core/499-gate-required-evidence-reconcile-20261110` | Retenir la protection, auditer la chaîne d'ancêtres |
| #516 | Worker : limiter les métadonnées UTF-8 avant Analyst/Critic/Policy | `agent/worker/457-fs147-action-binding-20261110` | Retenir le durcissement, vérifier compatibilité FS147 |
| #517 | Twin FS147 : refuser une provenance imbriquée non fiable | `feat/fs147-twin-adapter-qualification-20261108` | Retenir la protection, qualifier les dépendances |
| #529 | DR PostgreSQL : restauration jetable en conteneur PG16 | `fix/ci-postgres16-client-dr-20261110` | Retenir la qualification DR, sans effet sur données de production |
| #536 | n8n : exemple d'incident neutralisé | `ci/parallel-python-json-yaml-labs-20261110` | Priorité sécurité, **ne clôt pas** la révocation/audit historique #535 |
| #541 | Portal : filtrage des identifiants de preuve contradictoires | `agent/portal/461-operational-timeout-20261110` | Retenir après validation des composants |
| #544 | Portal : accessibilité du contexte d'historique Prometheus | `agent/portal/472-history-auth-denial-20261110` | Retenir après validation UX et sécurité |
| #547 | Portal : unifier les états timeout et annulation | `agent/portal/461-integrate-timeout-redaction-20261110` | Retenir après vérification des interactions avec #541/#544 |
| #549 | Installateur Compose isolé et hors ligne | `main` | Outil de qualification/déploiement, **pas remplacement automatique de l'existant** |
| #552 | Réseaux n8n↔PostgreSQL et simulator↔core ; images explicites | `feat/debian-isolated-compose-20261110` | Correctif dépendant de #549, conserver en brouillon |

Toutes les PR ci-dessus étaient en **Draft** lors de la lecture GitHub. Le fait qu'une PR soit `mergeable` ou qu'une CI ait été verte à un commit antérieur ne vaut ni revue indépendante ni qualification d'intégration.

## Ordre de consolidation proposé

1. **Sécurité en premier** : examiner #536 et ses ancêtres, obtenir la preuve de révocation/rotation et l'audit d'utilisation du secret historique (#535), faire valider par un reviewer indépendant.
2. **Contrats Core / Worker / Twin** : analyser les diffs de #515, #516, #517 et de leurs branches de base, sélectionner les changements fail-closed et tester ensemble les interfaces, la provenance, l'identité et l'exécution.
3. **Portal** : réconcilier #541, #544 et #547 avec leurs bases différentes ; vérifier qu'une consolidation ne réintroduit pas des états incohérents, fuites de preuves ou régressions d'accessibilité.
4. **Résilience** : intégrer les tests DR PG16 de #529 dans le pipeline, puis exiger une répétition sauvegarde/restauration avec preuves et sans accès prématuré à Debian.
5. **Qualification Debian** : conserver #549 + #552 comme chantier distinct ; DNS interne Docker autorisé, DNS externe interdit. Les IP statiques ne sont pas requises. Qualifier l'absence de requêtes DNS hors serveur, les réseaux et les images hors ligne avant toute intervention.

## Politique de fusion

- Ne pas fusionner les branches empilées directement et en bloc. Comparer chaque PR à `main`, identifier les commits hérités et reconstruire si nécessaire une branche de consolidation contrôlée, avec changements minimaux et tests d'intégration.
- Préserver la configuration, les données, volumes, secrets et services de la plateforme Debian existante ; documenter explicitement les migrations compatibles et leur retour arrière.
- Conserver les PR en Draft tant que les tests de la **tête courante**, les revues indépendantes et les gates de sécurité ne sont pas prouvés.
- Ne pas traiter la reconstruction isolée comme une substitution silencieuse de l'installation actuelle.
- **RELEASE HOLD** : aucune connexion SSH, migration, modification de volume, redémarrage, déploiement ni action LIVE sur `10.79.94.202` sans autorisation explicite et critères satisfaits.

## Points non encore démontrés

Diffs détaillés et ancêtres de toutes les PR, compatibilité inter-composants, CI sur les derniers commits, revue indépendante, audit de secrets, inventaire Debian actualisé, DNS externe bloqué, répétition DR, et plan de promotion sans perte de données.
