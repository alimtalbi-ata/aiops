Coordination nocturne autorisée, issue #462, dépôt alimtalbi-ata/aiops.
Lire AGENTS.md et les documents de continuité/architecture/catalogue/inventaire avant de coder.
Ce codex exec a été lancé par le superviseur hôte. Ne lancer aucun autre codex exec ni superviseur. Ne modifier ni supervisor.py ni test_supervisor.py ni cette mission pendant les cycles.
Échéance ferme 2026-11-10 11:00 Europe/Paris. Budget de cycle 540 secondes ; terminer et publier avant expiration.
Travail uniquement sur agent/integration/462-night-20261109 dans ce clone dédié. Ne toucher aucun autre checkout.
GitHub est le bus de livraison, pas les sept conversations. Lire résultats publiés Core #458, Worker #459, QA #68 et leurs PR/commentaires récents ; fetch origin et examiner branches/PR/historique avant tout code. Deux tentatives pertinentes maximum par blocage, puis tâches indépendantes.
Candidate de référence e0fc66c3bc8f56cace0074de2f0a07d5bb551303 ; candidate distante initiale 3218228ab4b0d24faa117b49d08272c8e025750a. La priorité PG du run 42699163023/job 129438966138 a déjà été corrigée par 8011ddd6ff0130e52500a0832db187759a0e1025 + e7c76514b8e98cb35a9594226e7106fde98a42aa ; run 42703074786 success vérifié. Ne pas refaire cette correction ; confirmer versions client/serveur et conserver tous les contrôles de restauration.
Examiner les diffs publiés, reproduire les défauts avec tests ciblés légers ; résoudre sur branche nocturne sans écraser ownership actif (demander arbitrage par compte rendu en cas de conflit). Pas de cherry-pick aveugle, pas de merge ni rebase automatique. Tests lourds exclusivement GitHub Actions existants ; aucun banc de charge Debian. Les anciennes mentions PREPARATION ONLY ne bloquent pas cette reprise isolée.
Autorisé : lire Git/gh, commit/push branche dédiée, créer/mettre à jour une seule PR DRAFT pour #462 ciblant agent/integration/462-isolated-candidate, publier les comptes rendus nécessaires. Réutiliser la PR nocturne existante. Ne jamais passer en ready ni fusionner. Ne pas modifier les docs canoniques partagées ; handoff distinct docs/handoffs/integration/night-20261109/ seulement.
Interdit : commandes distantes, merge, déploiement, restart, écriture production GLPI/PG, duplication tickets, changement secrets, permissions Docker, cron/Compose existants, contournement Policy/Critic/HITL. Aucun pilotage revendiqué des conversations. Préserver contrôles restauration et checkouts modifiés.
Chaque cycle : rapport local et compte rendu GitHub si résultat matériel, SHA exact, diffs, tests réellement exécutés, liens CI exact SHA, CODE/CI/DEBIAN/E2E distincts (UNKNOWN/NOT_VERIFIED si absent), risques et rollback (abandonner branche/PR, aucun déploiement). Mettre à jour latest-cycle.md avec UTC, livraisons examinées et prochaine action. Ne jamais inventer E2E PASS ou déploiement. En cas de checkout sale, examiner et préserver le travail interrompu avant de poursuivre.

AUTORISATION UTILISATEUR — AUTONOMIE DE LIVRAISON

Cette instruction remplace les restrictions antérieures « aucun merge ni déploiement » pour le développement de la plateforme AIOps.

Le coordinateur est autorisé à développer, modifier le code, corriger les tests, publier les branches et PR, fusionner les changements qualifiés et déployer sur Debian sans nouvelle confirmation utilisateur. Il ne doit pas attendre les propriétaires inactifs pour corriger un défaut reproduit.

Avant toute livraison :
- Vérifier les évolutions distantes et les opérations concurrentes.
- Tester le commit réellement livré ; ne pas supprimer ou affaiblir les contrôles pour obtenir une CI verte.
- Préserver les checkouts modifiés et identifier les sources et images réellement déployées.
- Utiliser un checkout propre, un verrou de déploiement unique et le mécanisme de livraison existant vérifié.
- Préparer sauvegardes et retour arrière avant toute modification de services ou de données.
- Déployer par changement limité, contrôler la santé et le parcours fonctionnel, puis revenir à la version précédente si les contrôles échouent.
- Ne pas désactiver authentification, Policy, Critic, HITL ou protections LIVE. Cette autorisation concerne la livraison de la plateforme, pas une autorisation de remédiation LIVE sur les systèmes qu’elle supervise.
- Ne pas publier de secrets ni effectuer de suppression irréversible de données sans autorisation spécifique.

Ne pas fusionner aveuglément une ancienne branche complète dans main. Réconcilier les corrections avec la branche cible et conserver les capacités existantes.

Priorité : transformer les défauts reproduits en corrections committées et testées, qualifier la candidate intégrée, puis livrer sur Debian si provenance, sauvegarde et rollback sont établis. Si un prérequis manque, travailler à le résoudre et poursuivre les tâches indépendantes.

À chaque cycle, consigner commits, tests, CI, merges, déploiements, version active et éventuel rollback. L’arrêt à 11:00 Europe/Paris reste applicable ; ne pas commencer un déploiement qui ne peut pas être contrôlé et terminé avant cette échéance.
