# Programme de démo AIOps : observabilité, portail, CMDB, logs et performance

**Date :** 2026-11-06  
**Statut :** plan de réalisation et qualification, **aucune modification de production autorisée**  
**Référence Worker :** [rapport de qualification FS-001D](../qualification/FS-001D-WORKER-QUALIFICATION-2026-11-06.md)

## État observé (FS.1000 partiel)

Sur SRV-DEB-05, l'inventaire transmis confirme notamment :

| Couche | Existant observé | Usage visé |
|---|---|---|
| Portail | `aiops2-rebuild-portal` — `aiops2-portal:fs621-explorers-candidate`, port hôte `7777` | Point d'entrée unique, parcours incident |
| Métriques | `aiops2-rebuild-prometheus` v3.14.0 ; `aiops2-rebuild-grafana` v13.2.2 | Graphiques séries temporelles, santé, SLO |
| Alerting | `aiops2-rebuild-alertmanager` v0.34.1 | Corrélation d'alertes et source du trigger |
| Logs et traces | Loki 3.5.0, Tempo 2.7.2, OTel Collector 0.123.0 | Timeline et preuves, liens traces/logs |
| CMDB / ITSM | GLPI 11.0.9 ; MariaDB | Actifs, relations, impacts, tickets |
| Données métier | PostgreSQL 16 (Core et Temporal séparés) | Runs, événements, evidence, tables en lecture seule |
| Workflow | Temporal 1.31, Core, Worker, Evidence, Policy, Intelligence, Twin | Orchestration de l'incident synthétique |

**À vérifier :** endpoints /metrics, schémas des API, sources du portail FS621, accès internes entre services, qualité des données GLPI/CMDB et Prometheus. L'exécution initiale de FS.1000 a échoué pendant `find` (permissions sur `reports`) *avant* ces contrôles ; le script est corrigé sur la branche pour reprendre la découverte.

## Expérience de démo visée

Une anomalie **synthétique**, clairement identifiée comme telle, affecte un composant (ex. SAN/Fabric) et dégrade un service métier :

1. **Trigger :** métrique Prometheus et alerte Alertmanager de démonstration, avec horodatage, règle, labels, seuil, lien vers série temporelle.
2. **Contexte :** enrichissement depuis GLPI/CMDB : CI touchés, application dépendante, propriétaire, criticité et impact.
3. **Investigation :** logs Loki, traces Tempo, métriques Grafana, Evidence et corrélation Core sur une même timeline.
4. **Intelligence :** proposition Analyst, validation/objections Critic, provenance et confiance visibles sans présenter les résultats synthétiques comme réels.
5. **Contrôle :** décision Policy `PASS/SIMULATE` (ou `BLOCKED`), checkpoint HITL et isolation DEMO explicites.
6. **Action :** remédiation *simulée* avec état avant/après du Twin, évaluation VERIFY et preuve de résultat.
7. **Synthèse :** run Temporal, durée totale, temps par étape, événements, impact CMDB et rapport exportable.

**Règle non négociable :** une alerte de démonstration ne déclenche pas une commande LIVE. Pas d'actions directes sur GLPI, bases métier ou infrastructure réelle sans autorisation et qualification dédiées.

## Lots de livraison incrémentaux

### Lot A — Inventaire et contrats de données

- Terminer FS.1000, identifier routes / métriques / types d'événements / données de CMDB.
- Mesurer ce que le portail FS621 affiche déjà ; documenter manques sans dupliquer les pages.
- Définir des endpoints de lecture seule pour `runs`, `evidence`, `gates`, `incidents`, `cmdb`, `metrics` et `logs`, selon les contrats existants.

**Critère d'acceptation :** inventaire reproductible, tableau de disponibilité API et plan d'intégration sans secrets.

### Lot B — Portail incident centré sur les preuves

- Page de run : séquence Core/Temporal, décision Policy, critic, badges `DEMO` vs `LIVE`, explication de `SIMULATE`.
- Cartes de métriques et graphe de latence/erreurs (lien Grafana/Prometheus).
- Explorateur de logs corrélé `run_id` et composant, avec pagination, filtres temporels et expurgation de secrets.
- Performance : latence P50/P95/P99, erreurs, consommation de ressources, taux de succès/blocked des workflows, temps par stage.

**Critère d'acceptation :** chaque élément visuel renvoie à une preuve datée et une source technique identifiable.

### Lot C — Topologie CMDB et vues bases de données

- Graphe CI → service → dépendance, impact de l'incident, filtres et légende.
- État de santé et historique associés aux CI, avec provenance et date de fraîcheur.
- Explorateur SQL **lecture seule**, requêtes préparées/whitelist, limite de lignes, aucune exposition de mots de passe ni tables sensibles.
- GLPI : utiliser API autorisée ou snapshots qualifiés, sans écriture sur le GLPI réel.

**Critère d'acceptation :** clic CI → incidents, métriques, logs, dépendances, owner et changements documentés.

### Lot D — Trigger Prometheus et storyboard E2E

- Fournir une alerte **synthétique isolée** réinjectable ; ne pas modifier les alertes de production.
- Vérifier doublons, idempotence et chemin alerte → incident Core → Temporal → Evidence → Policy → SIMULATE → VERIFY.
- Évaluer l'isolement réseau, les délais, les artefacts et les retours utilisateur.
- Tester le cas négatif `BLOCKED` et l'indisponibilité d'un service, pas uniquement le chemin nominal.

**Critère d'acceptation :** une démo reproductible avec traces corrélées, reset des données synthétiques et aucune remédiation LIVE.

## Principes UI et sécurité

- **Vraies sources :** pas de graphiques de métriques inventées ; données synthétiques clairement étiquetées et isolées.
- **Multi-environnements :** badge environnement sur chaque écran ; pas de confusion E2E et production.
- **Traçabilité :** dates absolues, liens sur `run_id`, `incident_id`, `evidence_id`, alert fingerprint, CI et trace ID.
- **Performances :** chargement paginé, échantillonnage des séries, cache contrôlé, gestion explicite des API indisponibles.
- **Accès :** ne pas ajouter un endpoint SQL arbitraire ni exposer les tokens internes au navigateur.
- **Livraison :** modifications GitHub, image candidate, qualification isolée, rollback documenté et aucune bascule production sans accord.

## Gouvernance GitHub

- Conserver les preuves Worker FS.993/998/999 et les risques de la PR [#446](https://github.com/alimtalbi-ata/aiops/pull/446) dans le rapport de qualification.
- Préférer une **PR dédiée** aux changements de portail/observabilité pour isoler revue UI, données et sécurité de la PR Worker #446.
- Documenter chaque lot avec preuves E2E, captures vérifiables, schémas de flux et état des endpoints.
