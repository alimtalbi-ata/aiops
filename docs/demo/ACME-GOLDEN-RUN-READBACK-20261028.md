# ACME Golden DEMO — lecture du Run canonique (2026-10-28)

**Portée :** code proposé dans une PR empilée sur #80. Aucune lecture réelle du Core, de GLPI ou de Debian n'a été effectuée dans ce lot.

Le portail ajoute `GET /api/demo/acme-run/{run_id}`, protégé par le **jeton opérateur de lecture** `AIOPS_PORTAL_READ_TOKEN` déjà utilisé par le NOC. L'authentification est vérifiée **avant** de lire le fixture local ou d'interroger Core. Sans jeton configuré : 503 ; sans autorisation : 401. Les erreurs ne divulguent pas de détails Core.

Le lecteur réutilise `noc_correlation._read_core_run` : un GET borné sur le Core interne `aiops2-core:810`, sans proxy ni redirection. Il n'ajoute aucune écriture, n'accède pas à PostgreSQL et ne fait aucun appel à GLPI.

Le rapprochement exige simultanément :
- `run_id` identique à l'identifiant demandé et conforme à `RUN-*` ;
- `incident_id=INC-ACME-DEMO-SAN-001` et `scenario_id=SCN-GOLDEN-PAYMENT-P1` ;
- `mode=DEMO`, version entière strictement positive et statut Core reconnu ;
- fixture ACME intact, marqué `SIMULATED_TARGET`, SHA-256 valide, sans preuve runtime ni ticket réel.

Un match retourne `MATCHED_UNATTESTED` et le statut/version **rapportés par Core**. Tout désaccord, y compris un Run LIVE, REPLAY ou STORY, retourne `UNKNOWN` **sans exposer les identifiants Core divergents**. Le ticket GLPI reste `null`, la corrélation GLPI `UNKNOWN` et les preuves d'exécution `NOT_TESTED`, même si Core rapporte `RESOLVED`.

Cette route est un **readback d'identité**, pas une preuve de succès Temporal, de résolution Payments, de disponibilité du chemin SAN redondant, de capture authentifiée ou d'une action LIVE autorisée. La vue d'impact reste purement synthétique. Les tests unitaires hors ligne utilisent des réponses Core injectées ; ils ne sont pas des tests d'intégration avec des services réels.

**Qualification future :** après fusion/rebase de #80, exécuter dans une CI éphémère le vrai Core + PostgreSQL + Temporal/Worker et vérifier le chemin d'exécution, puis relier le ticket via une observation GLPI indépendante (PR #69/#73) et une preuve d'association canonique. Tant que ces preuves manquent, afficher `UNKNOWN`. Ne pas réutiliser le jeton de lecture comme jeton d'écriture DEMO.

**Rollback :** revert de la PR sans migration ni état à restaurer ; le nouveau GET est strictement additif.
