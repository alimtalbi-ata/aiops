# AIOps2 — Référentiel technique durable

**Branche de référence :** `feat/portal-7777-observability-cmdb`  
**Environnement observé :** Debian `SRV-DEB-05`, projet Docker Compose `aiops2-rebuild`.  
**Sources :** `compose.yml`, `README.md`, `app/*`, `db/migrations/`, `scripts/fs/`, résultats FS1130–FS1139 rapportés par l'opérateur.

> **Convention impérative :** `CODE` = implémenté dans GitHub ; `TEST_ISOLÉ` = testé avec doubles/mocks ; `OBSERVÉ` = démontré sur les conteneurs ou la base ; `NON_VALIDÉ` = non prouvé en environnement réel. Ne jamais confondre ces statuts.

## 1. Architecture et responsabilité

Flux logique : **Portal → Core → Temporal/Worker → Twin / Evidence / Intelligence (Analyst, Critic) / Policy → registres Core et observabilité**. GLPI est la frontière ITSM : un incident Core n'est pas automatiquement un ticket GLPI tant que la création n'a pas été confirmée. n8n est une frontière d'intégration et **ne détient pas l'état canonique des runs**.

| Composant | Responsabilité / interface | Référence |
|---|---|---|
| Portal | UI, Explorer, KPI, Copilot, lecture Core | `app/portal/main.py`, `app/portal/kpi_views.py` |
| Core | incidents, runs, événements, commandes, registre canonique, API GLPI/KPI (code FS1136) | `app/core/main.py`, `app/core/glpi_*.py` |
| Worker / Temporal | orchestration des étapes et activités, Analyst/Critic, politiques et événements | `app/worker/main.py`, `app/worker/workflow.py` |
| Twin | état / scénarios simulés | `app/twin/` |
| Evidence | preuves et provenance | `app/evidence/` |
| Policy | décisions, garde-fous, HITL, interdiction d'effets LIVE non approuvés | `app/policy/` |
| Intelligence | appels modèles Analyst/Critic, télémétrie LLM en code | `app/intelligence/` |
| Copilot | interface de requêtes via Portal | `app/copilot/` |
| PostgreSQL Core | schéma `aiops`, incidents, runs, événements et registres | `db/migrations/` |
| Temporal + PostgreSQL | orchestration durable et stockage Temporal séparé | `compose.yml` |
| GLPI + MariaDB | tickets ITSM et base `glpi` | `compose.yml`, `docs/GLPI-API-OPERATIONS.md` |
| n8n | intégrations externes, pas source de vérité des runs | `compose.yml` |
| Prometheus, Grafana, Alertmanager | collecte, visualisation, alerting | `compose.yml`, `config/` |
| CloudBeaver | accès SQL administré, notamment Core, Temporal et GLPI | `docs/STACK-OPERATIONS-AND-QUALIFICATION.md` |

**Ne pas inférer l'état de déploiement à partir du code GitHub.** La branche contient des changements FS1131/FS1133/FS1136 non démontrés comme déployés dans les conteneurs.

## 2. Services et accès

Les ports internes observés dans le code incluent Core 810, Twin 811, Evidence 812, Policy 813, Copilot 814, Worker 815, Intelligence 817, Portal 777. Le Portal est publié en production sur le **port hôte 7777**. GLPI est exposé via son port interne 80 et le port hôte configurable `AIOPS_GLPI_HOST_PORT` (valeur par défaut Compose : 8080). Les ports effectifs doivent être vérifiés par `docker inspect` / `docker compose ps` : **les valeurs par défaut ne sont pas des mesures runtime**.

Le déploiement isolé documenté dans `docs/DEPLOYMENT-ISOLATED-REBUILD-RUNBOOK.md` utilise des ports hôtes alternatifs. Ne pas mélanger les conventions des deux modes.

## 3. Contrats API fondamentaux

- `POST /api/incidents` (Core, authentifié) : enregistre un incident `incident_id=INC-<external_id>`. `synthetic=true` indique un incident DEMO ; cela n'implique pas à lui seul une création GLPI dans les conteneurs actuellement déployés.
- `POST /api/scenarios/register`, `POST /api/runs`, `POST /api/runs/{run_id}/execute` : scénario et exécution ; voir `scripts/fs/FS.1130-50-incident-demo-e2e-campaign.sh`.
- `GET /api/incidents` : registre Core ; `GET /api/runs` : **100 runs les plus récents**, pas un inventaire historique complet ; `GET /api/runs/{id}` : détails, événements et étapes.
- `GET /api/kpi/glpi` : endpoint **CODE FS1136**, nécessite déploiement de Core et table de corrélation.
- `GET /kpi` : page Portal **CODE FS1131/FS1136**, non attestée déployée sur 7777.

Les écritures Core exigent un jeton interne. Les secrets ne doivent jamais être affichés, committés ni copiés dans les rapports.

## 4. Sémantique métier

`incident` = alerte/événement enregistré dans Core ; `run` = instance de workflow Temporal ; `ticket GLPI` = objet ITSM distinct créé par l'API GLPI. Les compteurs doivent être distincts. Un run `BLOCKED` par Policy n'est pas automatiquement un échec technique. `DEMO` est synthétique et doit être identifiable ; **aucun effet de remédiation LIVE ne doit être déduit de la création d'un ticket**.

Règle métier demandée : chaque nouvel incident DEMO ou LIVE doit donner lieu à un ticket GLPI réel confirmé. Dans GitHub, le drapeau `AIOPS_GLPI_TICKETS_REQUIRED=true` déclenche ce comportement côté Core (`app/core/glpi_ingest.py`), mais son activation et sa qualification en production sont **NON_VALIDÉES**.

## 5. Carte documentaire

- `docs/GLPI-API-OPERATIONS.md` — REST, jeton technique, restrictions IP, corrélation, activation et incidents connus.
- `docs/STACK-OPERATIONS-AND-QUALIFICATION.md` — exploitation, campagnes FS, limites des KPI, matrice de preuves.
- `docs/DEPLOYMENT-ISOLATED-REBUILD-RUNBOOK.md` — installation isolée.
- `docs/SECURITY.md` — gestion des secrets et authentification.
- `compose.yml` — topologie déclarative, **pas** état réel garanti.
- `scripts/fs/` — scripts de qualification, chacun avec son périmètre.

## 6. Politique de maintenance de la connaissance

Toute fonctionnalité ajoutée doit inclure : objectif, code source, endpoint/contrat, configuration, réseaux, stockage, sécurité, procédure de test, résultat attendu, rollback, KPI, limites et statut `CODE/TEST_ISOLÉ/OBSERVÉ/NON_VALIDÉ`. Mettre à jour cette carte et le runbook spécialisé **dans le même commit que le changement**. Ajouter les nouveaux incidents de diagnostic et leurs causes prouvées ; ne pas enregistrer de secrets ou d'adresses privées sensibles inutilement. Un rapport de test ne remplace pas une preuve de déploiement.
