# AIOps2 — suivi horaire, baseline du 2026-11-08

## Objectif non négociable
Une plateforme AIOps2 fonctionnelle sur SRV-DEB-05, démontrable de bout en bout, installable chez un client ITIL 4 via connecteurs interchangeables. Le Digital Twin est uniquement un banc de qualification.

## Statut par dimension (ne jamais confondre)
| Dimension | État et preuve |
| --- | --- |
| CODE | Kits architecture et réconciliation; correctif run_linkage_gate.py commit 9f8fb53; gate transversal platform_readiness_gate.py commit 45b17fcc; probe GLPI commit 06cd21af |
| CI | Workflow aiops2-reconciliation-audit.yml ajouté; aucun succès GitHub Actions attesté à la création de ce suivi |
| DEBIAN | Correctif run_linkage_gate.py SHA256 8ee47e8f837b84a09fdfa3790fa72d4d91e47ad0ab4caed3892d2836d69bf269 exécuté sur SRV-DEB-05; reçu /home/aiops/aiops2-deployment-receipt-20261108T123409Z.json |
| E2E | FS1250: Core/Evidence/Critic-Policy PASS; Core GLPI xref MISSING; Temporal/Worker et HITL UNVERIFIED; gate HOLD |
| PRODUIT | Installateur client, adaptateurs multiples, recette multi-scenarios, rollback, observabilité de bout en bout : non qualifiés |

## Dernières observations Debian communiquées
78 conteneurs (59 running, 18 exited, 1 created); services Core 810, Twin 811, Evidence 812, Policy 813, Worker 815, Intelligence 817, GLPI 80, Temporal 7233, PostgreSQL 5432. Ces données sont une photographie passée, pas un état temps réel.

## Contrat de reporting
L'automatisation existante « AIOps2 — intégration et rapport horaire » est le rapporteur unique à chaque heure; elle conserve le rôle de coordination des quatre autres tâches. Capacité du plan : cinq tâches, donc aucune sixième tâche ajoutée. À chaque cycle: vérifier les preuves, produire un rapport même sans changements, enregistrer les SHA/PR/CI/DEBIAN/E2E et une priorité exécutable. Ne pas présenter le code sur GitHub comme déployé.

## Priorité immédiate
1. Exécuter le gate transversal platform_readiness_gate.py sur Debian et conserver le reçu, sans écriture live.
2. Identifier un mécanisme de livraison contrôlé via cron existant, runner GitHub ou agent connecté, en distinguant capacité constatée et hypothèse.
3. Qualifier la chaîne source→Core→intelligence/Critic→Policy→Temporal/Worker→Evidence→Portal→ITSM, avec cas de refus et scénario non-GLPI.
4. Déployer les correctifs par composants avec backup/rollback, smoke tests, suivi de version et preuve d'installation.
