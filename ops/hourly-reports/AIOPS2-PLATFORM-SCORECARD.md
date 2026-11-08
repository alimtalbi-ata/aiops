# AIOps2 — tableau de pilotage factuel (baseline 2026-11-08)

**Objectif:** produit AIOps2 multi-composants, fonctionnel sur Debian, démontrable E2E, installable chez des clients, connecteurs remplaçables; Twin = qualification facultative.

## Règles de vérité
- **CODE**: commit GitHub + chemin; **CI**: run et résultat; **DEBIAN**: preuve hôte, empreinte et date; **E2E**: parcours et assertions réelles. Aucun statut ne remplace les autres.
- Une observation ancienne ne devient pas « état actuel » sans nouveau relevé.
- Chaque rôle doit remettre une preuve et une prochaine action vérifiable, ou signaler explicitement l'absence de livraison.
- Le rapport horaire doit mettre à jour cette page ou créer un journal daté et référencé. Ne pas inventer de CI verte ni de déploiement.
- **Interdiction de dérive:** GLPI et FS147 ne sont que des composants/scénarios; le succès = plateforme complète + packaging client.

## Tableau de référence
| Axe | Preuve connue | Statut |
| --- | --- | --- |
| Infra Debian | bootstrap exécuté 2026-11-08T12:43:58Z, cron platform_hourly H:17, SHA gate 954b6ca8bbc928a0153855b68a79f3f022c8209bb34f9b078a791c83f3a7ff2b | INSTALLED (collector); plateforme E2E non qualifiée |
| Transport Debian → GitHub | cron aiops-debian-reporter et aiops-publish-report présents chaque minute (sortie crontab) | CRON_PRESENT; publication du nouveau gate non prouvée |
| Transport GitHub → Debian | cron poll.sh présent chaque minute | CRON_PRESENT; promotion/déploiement effectif non prouvé |
| Core | FS1250 run API, DB, evidence, critic outbox PASS, rapport 2026-11-08T12:34:09Z | PARTIAL |
| Policy / HITL | critic outbox reconciled; liaison approbation/action non vérifiée | PARTIAL |
| Temporal / Worker | conteneurs antérieurement sains; historique workflow/activité non vérifié | UNVERIFIED E2E |
| Evidence | API evidence FS1250 PASS | PARTIAL |
| Twin | summary antérieurement 35 nœuds; isolation/qualification E2E non prouvée | PARTIAL |
| Intelligence / RAG / Critic | étapes FS1250 observées, blocage critique cohérent; intégration complète non prouvée | PARTIAL |
| Portal | parcours navigateur et affichage de vérité non prouvés dans ce suivi | UNVERIFIED |
| ITSM | GLPI #201 observé dans UI, absence de Core xref FS1250 | PARTIAL |
| Observabilité / sécurité | pas de gate global exécuté rapporté | UNVERIFIED |
| Packaging client / adaptateurs | architecture documentée; installateur multi-environnement non démontré | NOT_DONE |
| CI | workflow audit présent; exécution verte non attestée | UNVERIFIED |

## Cadence opérationnelle
- H:00 Intégration (rapport), H:12 Core, H:24 Worker, H:36 Twin, H:48 Portal; horaires Europe/Paris, cinq tâches actives.
- Debian: poll, reporter, publisher chaque minute; fs-watch toutes les 10 minutes; gate plateforme H:17.
- Les tâches ne s'exécutent pas de manière autonome entre leurs créneaux; le cron Debian n'exécute que ce qui est réellement configuré.

## Priorités sans dérive
1. Vérifier et archiver un rapport platform_readiness réel et sa publication dans ops/debian-runtime-reports.
2. Lire et qualifier les règles exactes de poll.sh, les branches autorisées, les prérequis et le rollback.
3. Faire passer des gates E2E transversaux (un incident non-GLPI inclus), sans contourner Policy.
4. Versionner packaging client, matrice d'adaptateurs et recette de déploiement reproductible.

## Contrat de chaque rapport
Horodatage; livraisons et SHAs depuis le rapport précédent; CI run; reçu Debian; résultats E2E; écarts par composant; bloqueur; prochaine action; verdict `ON_TRACK` ou `AT_RISK` et justification. En l'absence de preuves nouvelles: `NO_NEW_EVIDENCE`.
