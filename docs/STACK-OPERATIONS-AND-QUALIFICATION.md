# AIOps2 — Exploitation, validation et historique de qualification

## 1. Environnement de référence

Serveur observé : `SRV-DEB-05`, utilisateur `aiops`, Docker rootless, dépôt local `/home/aiops/aiops2-v2-delivery`, branche `feat/portal-7777-observability-cmdb`. Le conteneur Portal de production est `aiops2-rebuild-portal` et publie `7777:777` ; **ne pas le reconstruire, redémarrer ou remplacer sans autorisation distincte**.

Les conteneurs connus comprennent Core, Worker, Twin, Evidence, Policy, Intelligence, Copilot, Portal, PostgreSQL Core, Temporal, PostgreSQL Temporal, GLPI, MariaDB GLPI, n8n, Prometheus, Grafana et Alertmanager. CloudBeaver a été configuré sur le port hôte 8978, avec un espace de travail persistant `aiops2-cloudbeaver-workspace` et des connexions Core, Temporal, GLPI. Cette liste mêle inventaire Compose et observations antérieures : vérifier le runtime avant d'affirmer qu'un conteneur précis est actuellement sain.

## 2. Bases de données et source de vérité

| Base | Service / réseau connu | Rôle |
|---|---|---|
| PostgreSQL Core | `aiops2-rebuild-postgres` / `aiops2-rebuild-data` | `aiops.incidents`, `aiops.runs`, `aiops.run_events`, données canoniques |
| PostgreSQL Temporal | `aiops2-rebuild-temporal-postgres` / `aiops2-rebuild-temporal-data` | persistance des workflows Temporal |
| MariaDB GLPI | `aiops2-rebuild-glpi-db` / `aiops2-rebuild-integration` | objets ITSM et configuration API GLPI |
| CloudBeaver | port hôte 8978 | interface SQL ; **pas** source canonique des incidents |

La base Core et la base Temporal sont distinctes. Les états des workflows ne doivent pas être inférés uniquement à partir des événements Core ni inversement. Un ticket GLPI doit être vérifié par son identifiant réel.

## 3. Campagnes et niveau de preuve

| FS | Objet | État attesté | Limite |
|---|---|---|---|
| FS1128 | tests incidents/Policy | 13/13 PASS isolés | pas de qualification LIVE |
| FS1129 | sondes HTTP | **NON VALIDÉ** | exécution `docker run ... python -` sans `-i`, sondes non exécutées |
| FS1130 | 50 incidents DEMO | campagne lancée ; 24 incidents FS1130 observés plus tard | pas 50 workflows terminés ; pas de tickets GLPI |
| FS1131 | page KPI Portal | PASS isolé | non attestée déployée sur 7777 |
| FS1132 | rapport KPI offline | PASS tests | dépend du rapport réel FS1130 |
| FS1133 | télémétrie LLM | PASS isolé | non déployée ; 0 événements LLM observés dans FS1135 |
| FS1134 | intégration Intelligence/Portal mock | PASS isolé | provider HTTP simulé, pas Worker/Temporal réel |
| FS1135 | cohérence API Core/PostgreSQL | PASS lecture seule | 100 derniers runs seulement ; 22 runs FS1130, 0 terminaux |
| FS1136 | création GLPI DEMO et KPI | PASS mock isolé | aucun ticket réel créé ; registre absent à la date du test |
| FS1137 | endpoints GLPI | PASS lecture seule | routes répondent mais authentification non prouvée |
| FS1138 | jeton GLPI existant | diagnostic terminé | `ERROR_NOT_ALLOWED_IP`, authentification refusée |
| FS1139 | réseau et schéma filtrage IP | diagnostic terminé | lignes effectives de `glpi_apiclients` non encore examinées |

**Règle :** un `FINAL_STATUS=PASS` valide uniquement les assertions réellement exécutées. Il ne prouve pas une fonctionnalité E2E si des mocks sont utilisés ou si un service n'est pas déployé.

## 4. KPI : définitions et limites

- **Incidents Core** : lignes `aiops.incidents` ; peut être supérieur au nombre de runs.
- **Runs** : lignes `aiops.runs`, distinctes des incidents.
- **Tickets GLPI confirmés** : associations `glpi_ticket_links` avec état `CONFIRMED` et identifiant retourné par l'API.
- **Tickets incertains** : `UNKNOWN` ; ne jamais compter comme succès.
- **Taux de synchronisation FS1130** : `fs1130_tickets_confirmed / fs1130_incidents × 100` si dénominateur non nul ; préciser le périmètre.
- **Latence de création** : intervalle entre ouverture Core et confirmation GLPI, selon la définition du code ; peut inclure des retards de reprise.
- **Analyst/Critic** : métriques par événements et étapes ; `llm_telemetry` ne doit pas être inventée si le provider ne retourne pas l'usage des tokens.
- **Portal KPI** : lecture des 100 runs Core les plus récents et détails limités aux 50 runs FS1130 sélectionnés ; **pas un tableau historique exhaustif**.

## 5. Opérations sûres

Préférer les worktrees Git détachés dans `/tmp` pour tester les commits sans altérer le dépôt courant. Les diagnostics doivent être en lecture seule par défaut, ne jamais imprimer les secrets et annoncer explicitement les mutations. Les écritures GLPI créent des objets métier réels même pour DEMO. Déployer Core et Portal séparément ; préserver le portail de production 7777. Pour tout changement : sauvegarde, diff/configuration, test isolé, essai réel borné, mesure KPI, rollback documenté.

## 6. Points ouverts et prochaine qualification

1. Examiner les **lignes effectives** de `glpi_apiclients` (sans secrets) et la règle de plage IP qui refuse `initSession`.
2. Résoudre le chemin réseau Core → GLPI sans exposition excessive.
3. Confirmer le jeton d'application si requis, et le compte technique et ses permissions.
4. Tester **un seul ticket [DEMO] réel** et la corrélation Core ; rapprocher tout résultat incertain avant retry.
5. Activer le caractère obligatoire des tickets dans Core, tester le retour d'erreur, la reprise et la déduplication.
6. Reprendre les incidents FS1130 historiques uniquement après rapprochement des tickets GLPI préexistants.
7. Qualifier le KPI sur données réelles, puis planifier séparément le déploiement du Portal 7777.

## 7. Journal de décisions à maintenir

- **Décision métier** : DEMO et LIVE doivent créer un ticket GLPI réel.
- **Décision sécurité** : pas de remédiation LIVE non approuvée ; création ITSM ≠ remédiation.
- **Décision production** : Portal 7777 non modifiable sans accord séparé.
- **Décision de preuve** : distinguer code GitHub, test isolé, exécution réelle et déploiement effectif.
- **Décision documentaire** : toute nouvelle fonctionnalité ou correction ajoute sa procédure d'exploitation et sa preuve dans ce référentiel.
