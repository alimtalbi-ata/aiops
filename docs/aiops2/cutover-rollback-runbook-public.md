# AIOPS2 — Runbook de bascule et retour arrière (PROJET NON EXÉCUTABLE)

> **STATUT : PRÉPARATION SEULEMENT — BASCULE NON AUTORISÉE.** Document public expurgé, sans identifiants, secrets, valeurs d'environnement ni commandes de mutation. La validation d'un document ne vaut pas autorisation d'exécution.

## 1. Périmètre vérifié

21 services candidats : alertmanager, cloudbeaver, copilot, core, evidence, glpi, glpi-db, grafana, intelligence, n8n, policy, portal, postgres, prometheus, simulator, temporal, temporal-postgres, temporal-ui, test-llm, twin, worker.

- 21/21 conteneurs historiques en cours d'exécution ; 14 healthy, 0 unhealthy, 7 sans healthcheck.
- 21/21 noms de conteneurs occupés ; aucun ne peut être simplement recréé sous le même nom sans coordination.
- 20 conteneurs avec politique `unless-stopped`, un avec `no` (`test-llm`).
- 11 montages de volumes et 11 bind mounts ; 11 volumes et 7 réseaux externes dans le brouillon.
- 8 publications de ports déclarées dans le brouillon : alertmanager, cloudbeaver, glpi, grafana, n8n, portal, prometheus, temporal-ui.
- 21 références à des fichiers d'environnement privés vérifiées ; syntaxe du brouillon Compose validée.
- Aucune dépendance `depends_on` déclarée dans le brouillon : **dépendances applicatives non encore exhaustivement modélisées**.
- Temporal dépend historiquement de temporal-postgres et d'un job de schéma ; jobs historiques schema et namespace terminés avec succès (exit 0). **Ne pas les réexécuter automatiquement.**
- `test-llm` reste optionnel sous profil `test`.

## 2. Conditions obligatoires avant approbation

1. Identifier le responsable de la fenêtre de maintenance, la durée maximale d'interruption et le décideur de retour arrière.
2. Vérifier que tous les fichiers Compose, chemins de bind mounts, réseaux, volumes, images épinglées, politiques de redémarrage, ports et configurations privées sont exacts. **Ne pas publier les valeurs privées.**
3. Construire et approuver une matrice des dépendances applicatives réelles, y compris celles qui ne figurent pas dans les labels Docker.
4. Produire une sauvegarde cohérente au point de bascule, avec une méthode de quiescence ou d'arrêt contrôlé adaptée à chaque base et service écrivant sur les volumes.
5. Vérifier les archives, les procédures de restauration, les droits et les secrets nécessaires ; les essais structurels SQL existants ne prouvent pas l'intégrité de toutes les lignes métier ni des volumes.
6. Disposer d'une copie hors serveur appropriée. Les archives préparatoires actuelles sont uniquement locales.
7. Définir les critères d'acceptation par service, les contrôles d'intégrité des données et les seuils déclenchant un retour arrière.
8. Vérifier la possibilité de restaurer les conteneurs historiques, leurs noms, leurs paramètres et leurs montages. Ne jamais supposer que Compose peut adopter des conteneurs créés par d'autres projets.
9. Valider la procédure de changement de nom/libération des noms et ports, le comportement `unless-stopped`, ainsi que les effets d'un redémarrage du daemon rootless.
10. Obtenir une **autorisation explicite distincte** pour la vague considérée, après revue du plan et des sauvegardes.

**Critère NO-GO :** une seule condition critique non satisfaite suffit à suspendre la bascule.

## 3. Séquencement — proposition à valider, non exécutable

Le découpage ci-dessous est une grille de préparation, **pas un ordre définitif de déploiement**. Les dépendances réelles peuvent imposer un autre ordre.

| Groupe | Services | Vérifications spécifiques |
| --- | --- | --- |
| Observabilité | prometheus, alertmanager, grafana | Conservation des séries, règles, tableaux de bord, accès et ports |
| Interfaces | portal, cloudbeaver, temporal-ui | Montages, authentification, routes et ports |
| Applications | glpi, n8n, copilot, simulator | Accès aux bases, traitements, migrations éventuelles, données |
| Services AIOPS2 | core, intelligence, policy, evidence, twin, worker | Contrats API, flux, tâches en cours, accès aux montages |
| Données et orchestration | postgres, glpi-db, temporal-postgres, temporal | Sauvegarde transactionnelle, compatibilité de schéma, absence de double écrivain |
| Optionnel | test-llm | Profil test uniquement ; ne pas activer implicitement |

Les bases de données et composants à état **ne doivent pas être déplacés simplement en dernier ou en premier** : le séquencement doit résulter de la matrice de dépendances et des conditions de cohérence.

## 4. Fiche obligatoire pour chaque vague

Avant exécution, renseigner et faire approuver :

- Services, noms de conteneurs historiques et noms futurs ; propriétaire et heure de la fenêtre.
- Dépendances amont/aval et services à mettre en maintenance.
- Point de sauvegarde, horodatage, méthode, empreintes et preuve de restauration.
- Plan de prévention des écritures concurrentes et des redémarrages automatiques.
- Ports et accès à préserver ; réseaux, alias et volumes à réutiliser.
- Actions précises de remplacement, préalablement relues et validées ; **aucune commande destructive générique**.
- Vérifications : état, santé, connectivité, fonctions métier, intégrité des données, métriques.
- Durée d'observation et critères chiffrés GO/NO-GO.
- Procédure exacte de retour arrière et traitement des écritures intervenues après le point de sauvegarde.
- Décision signée : autorisation, validation finale ou retour arrière.

## 5. Principes du remplacement contrôlé

1. Geler les modifications de configuration et prendre un instantané d'inventaire.
2. Placer les producteurs/consommateurs concernés en maintenance selon les dépendances validées ; éviter toute double écriture.
3. Effectuer et vérifier la sauvegarde cohérente de la vague.
4. Préserver les conteneurs historiques et leurs métadonnées ; planifier la libération des noms et ports **sans suppression prématurée**.
5. Prévenir les redémarrages concurrents, notamment pour les 20 conteneurs `unless-stopped`.
6. Démarrer uniquement les services explicitement autorisés, avec leurs ressources externes et leurs paramètres vérifiés.
7. Exécuter les tests de santé, de fonctionnalité et de données ; surveiller la fenêtre d'observation.
8. Ne passer à la vague suivante qu'après acceptation formelle.

## 6. Retour arrière — deux chemins distincts

**A. Retour arrière sans modification incompatible des données :**
- Interrompre les nouvelles écritures et le nouveau service selon le plan approuvé.
- Confirmer que les données et schémas restent compatibles avec l'ancien binaire.
- Rétablir noms, ports, réseau, configuration et ancien conteneur ; rétablir ensuite les accès.
- Vérifier l'intégrité et documenter l'incident.

**B. Retour arrière avec données modifiées ou incompatibles :**
- Déclencher le protocole de restauration cohérente ; ne pas redémarrer aveuglément l'ancien binaire sur un schéma modifié.
- Déterminer explicitement le sort des écritures intervenues après la sauvegarde : elles peuvent être perdues sans journalisation ou mécanisme de réconciliation.
- Restaurer les données et configurations correspondantes, vérifier les privilèges et effectuer les tests métier avant réouverture.

Dans les deux cas, **ne pas supprimer les conteneurs historiques ni les sauvegardes pendant la période de validation**.

## 7. Risques spécifiques déjà connus

- **Prometheus :** publication souhaitée sur le port LAN 9090, différente de la publication effectivement constatée avant bascule ; tester la disponibilité et l'absence de conflit.
- **CloudBeaver et Portal :** conserver leurs publications réseau historiques, y compris l'adresse d'écoute.
- **Temporal :** jobs schema et namespace déjà exécutés avec succès ; ne pas les relancer automatiquement ; vérifier la compatibilité de la base.
- **MariaDB GLPI :** la sauvegarde SQL préparatoire est une sauvegarde applicative, pas un export complet des comptes et privilèges administratifs.
- **PostgreSQL :** les exports préparatoires ont omis les mots de passe des rôles ; prévoir la restauration contrôlée des secrets et privilèges.
- **Bind mounts :** certains contenus peuvent être sensibles ; préserver chemins, modes et droits, sans les exposer publiquement.
- **Volumes :** les archives prises à chaud ne prouvent pas à elles seules la cohérence applicative.
- **Rootless Docker :** exécuter sous le bon utilisateur/contexte, sans basculer par inadvertance sur le daemon rootful.

## 8. État de validation

| Contrôle | État |
| --- | --- |
| Inventaire et précontrôles Compose | Validés statiquement |
| Restaurations SQL isolées | Importations et structures vérifiées |
| Comparaison exhaustive des données | Non réalisée |
| Restauration complète des volumes | Non validée |
| Dépendances applicatives | À compléter |
| Sauvegarde cohérente au cutover | À réaliser |
| Copie de sauvegarde hors serveur | Non confirmée |
| Procédures détaillées par vague | À rédiger et approuver |
| Autorisation de bascule | **NON** |

## 9. Publication et traçabilité

Ce document est publiable dans un dépôt public. Les sauvegardes SQL, archives de volumes et de montages, fichiers d'environnement, configurations brutes, jetons, mots de passe et données métier restent **hors GitHub public**. Suivi : [issue #555](https://github.com/alimtalbi-ata/aiops/issues/555).
