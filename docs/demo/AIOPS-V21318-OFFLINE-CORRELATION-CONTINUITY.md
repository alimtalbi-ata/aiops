# V2.13.18 — Corrélation ACME strictement hors ligne (candidat)
Date : 2026-10-22. Architecture : fixture `aiops.acme.demo.v1` → validation stricte → graphe CI inversé → chemins d'impact potentiels → hypothèses de corrélation.

## Contrat et limites
Les chemins de dépendance décrivent des relations déclarées, jamais une preuve de causalité. Fabric B est `UNKNOWN_NOT_MEASURED`. Analyst DGX, Critic et Policy sont `NOT_EXECUTED`/`NOT_EVALUATED`; aucun HITL, effet, ticket ou run LIVE n'est attesté. `SIMULATED_TARGET` est imposé. Les exports opérateur `OPERATOR_SUPPLIED_EXPORT` sont refusés par ce calculateur et nécessitent un pipeline de provenance séparé.

## Sécurité et qualification
Le moteur prévu est un CLI Python sans client HTTP ni code de mutation, `--apply` refusé; validation de schéma, identités, dépendances cycliques, actions autorisées et clés JSON dupliquées. Test local isolé du candidat : 12/12 unittest PASS (hors dépôt GitHub, ne constitue pas un succès CI). Aucune qualification sur les services Debian. Le fichier d'implémentation et les tests doivent être intégrés dans cette PR puis validés en CI avant de déclarer la livraison.

## Reprise Debian
Ne rien déployer automatiquement. Préserver le portail unique 17777 et les services GLPI/Grafana/n8n. Après revue de la PR et autorisation explicite : tests isolés, inventaire lecture seule, mapping GLPI vérifié, puis décision de déploiement distincte. Rollback Git : revenir au SHA parent du commit candidat; aucun rollback DB nécessaire (aucune écriture).
