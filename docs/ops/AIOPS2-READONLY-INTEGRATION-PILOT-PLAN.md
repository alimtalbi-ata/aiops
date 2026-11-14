# AIOPS2 — pilote d'intégration read-only (préproduction)

**Statut : plan de qualification uniquement. Aucun endpoint positif, aucune connexion réelle ni aucun accès production n'est déclaré par ce document.**

## But métier

Passer du scénario ACME synthétique à une démonstration sur des sources d'intégration contrôlées, sans perdre la chaîne de responsabilité :

**signal SAN → incident P1 → dépendance Payments → éléments de preuve → Analyst/Critic → Policy/HITL → simulation → postcheck indépendant → préparation ITIL.**

Le résultat attendu du pilote n'est pas une remédiation. C'est un dossier montrant, pour chaque transition, la source, l'identité du collecteur, l'horodatage, la portée tenant/entité, l'empreinte, le statut de vérification et la raison de tout refus.

## Règle de départ

Le scénario synthétique reste le parcours de référence et le plan de secours. Le pilote read-only utilise un tenant, un incident, une entité GLPI, un compte opérateur et des identifiants de service dédiés à l'environnement jetable. Ne jamais réutiliser un secret de production. Ne jamais importer de données client réelles dans les fixtures.

## Matrice des intégrations et preuves exigées

| Source | Lecture pilote autorisée | Preuve à conserver | Refus obligatoire |
|---|---|---|---|
| Grafana | Lire une alerte SAN de test et ses labels | URL/UID du dashboard, rule UID, labels, timestamp UTC, identité de service, réponse brute expurgée + SHA-256 | Alerte absente, tenant non résolu, timestamp invalide, provenance non vérifiable |
| n8n | Lire l'exécution d'un workflow de corrélation déjà lancé manuellement | Workflow ID, execution ID, statut, started/finished UTC, version du workflow, hash des entrées/sorties expurgées | Ne jamais démarrer/rejouer un workflow pendant la phase read-only |
| CMDB / GLPI | Lire un CI et un ticket de test via ACL native GLPI | Instance/entity/ticket/CI IDs, profil GLPI, droits natifs effectifs, acteur humain corrélé, réponse expurgée + SHA-256 | Token d'application seul, entité implicite, droit humain non vérifié, xref absent/invalide/rejoué |
| OIDC | Authentifier un opérateur pilote | Issuer, audience, subject dérivé issuer+sub, auth_time/amr, kid/JWKS, décision de mapping de groupes versionnée | Simulation, issuer/audience inconnus, token expiré, JTI révoqué, MFA/assurance insuffisante |
| Core / Temporal | Inspecter un workflow préexistant en lecture seule | Core run ID, workflow ID, start intent, historique initial, comparaison des paramètres, résultat UNKNOWN/MATCH/MISMATCH | Toute tentative de start/restart, historique incomplet, identité ou paramètres divergents |
| Policy / HITL | Afficher une décision de simulation et l'identité de l'approbateur | Policy version/hash, décision, actor subject, tenant, portée, expiration et journal d'audit | Approbation automatique, principal absent, approbateur hors scope |
| Postcheck | Comparer des observations indépendantes avant/après sur une cible de test | Source distincte de l'action, mesure horodatée, seuil attendu, hash, verdict et identité du vérificateur | Réutiliser le reçu d'action comme preuve de résultat ou convertir une absence en PASS |

## Phases et portes de sortie

### P0 — Préparation isolée

- Environnement éphémère identifié, propriétaire, durée de vie et procédure de destruction documentés.
- OIDC de test, Grafana de test, n8n de test, GLPI de test et PostgreSQL/Temporal jetables.
- Comptes humains et de service distincts; permissions minimales vérifiées.
- Aucun secret dans Git, les artefacts, les journaux ou les captures.

**Sortie P0 :** inventaire des endpoints, propriétaires, scopes, comptes et preuves d'isolation approuvé. Sinon STOP.

### P1 — Identité et périmètre

- Authentifier un opérateur avec l'IdP de test.
- Vérifier issuer, signature JWKS, audience, exp/nbf, JTI/révocation, auth_time/amr et mapping versionné.
- Prouver les refus A/B: autre tenant, autre entité, autre ticket, acteur révoqué, token rejoué.
- Mesurer zéro appel upstream et zéro donnée partielle pour chaque refus.

**Sortie P1 :** principal Core-owned et grants tenant/acteur qualifiés. Sinon STOP; aucune lecture GLPI.

### P2 — Collecte read-only

- Lire une alerte Grafana de test existante.
- Lire une exécution n8n déjà achevée; aucune création ou relance.
- Lire un CI/ticket GLPI de test après vérification de l'ACL native du compte humain et de l'association xref signée.
- Corréler les éléments par tenant, entity, incident et run; conserver les réponses expurgées et leurs hashes.

**Sortie P2 :** chaque fait affiché possède une provenance indépendante et un scope prouvé. Les absences restent UNKNOWN.

### P3 — Raisonnement et gouvernance

- Analyst produit des hypothèses liées à des citations de sources.
- Critic identifie les contre-preuves et les lacunes.
- Policy décide sur une version immuable; HITL identifie l'humain et sa portée.
- Toute action demeure simulation-only; aucune écriture GLPI ou exécution n8n.

**Sortie P3 :** revue humaine documentée; aucune autorisation implicite. Sinon STOP.

### P4 — Postcheck indépendant et dossier de démonstration

- Mesurer l'état cible via une source distincte de la commande simulée.
- Vérifier la fraîcheur, la cohérence temporelle et la provenance de chaque preuve.
- Générer un dossier avec commit, versions, identifiants expurgés, timestamps, décisions, hashes et résultats de refus.
- Rejouer les tests A/B et vérifier zéro effet externe.

**Sortie P4 :** GO limité à la démonstration read-only sur environnement de test. La récupération réelle reste UNKNOWN tant qu'une action contrôlée et un postcheck indépendant ne sont pas explicitement qualifiés.

## Scénario de répétition client (15 minutes)

1. **0–3 min — Impact métier :** montrer le signal SAN, l'incident P1 et le service Payments avec IDs corrélés.
2. **3–6 min — Preuves :** ouvrir l'alerte Grafana et les éléments CMDB/GLPI autorisés; distinguer données lues et champs absents.
3. **6–9 min — Analyse :** présenter hypothèses Analyst, objections Critic et sources citées.
4. **9–11 min — Gouvernance :** montrer policy, identité HITL, décision et refus explicites.
5. **11–13 min — Temporal :** inspecter uniquement un workflow préexistant; expliquer UNKNOWN/MATCH/MISMATCH sans assimiler MATCH à un succès métier.
6. **13–15 min — Vérification :** présenter le postcheck indépendant, les preuves manquantes et la préparation ITIL sans clôture ni écriture.

## Critères de NO-GO

Arrêter le pilote si une source n'est pas authentifiée, si le scope tenant/entity n'est pas démontré, si un service peut écrire/rejouer, si une réponse upstream est présentée sans provenance, si une donnée partielle fuit après refus, si le postcheck dépend de la même source que l'action, ou si un état inconnu est affiché comme PASS.

## Statut de décision

- **GO actuel :** démonstration synthétique et contrôles CI du commit qualifié.
- **GO futur conditionnel :** pilote read-only en préproduction, après P0–P4.
- **NO-GO :** production, écriture GLPI, démarrage/rejeu automatique Temporal/n8n, remédiation LIVE et clôture ITIL automatique.

Aucun merge, déploiement, migration de production, connexion à un IdP/GLPI de production ou usage de secret réel n'est autorisé par ce plan.

## Parcours Portal démontrable — observation Grafana non attestée

- Cockpit incident SAN P1 → Payments P2 : `GET /demo/acme-incident-cockpit`.
- Observation Grafana **synthétique et locale** : `GET /demo/acme-grafana-pilot-preview`.
- Le second écran présente un signal candidat, l'identifiant tenant déclaré, l'horodatage et un SHA-256 local. Il reste `UNKNOWN / BLOCKED` ; ni le transport ni l'ACL native Grafana ne sont attestés.
- Registre de départ : `docs/ops/AIOPS2-READONLY-PILOT-EVIDENCE-REGISTER.template.json`. Vérification négative attendue : `python scripts/validate_aiops2_readonly_pilot_register.py docs/ops/AIOPS2-READONLY-PILOT-EVIDENCE-REGISTER.template.json` retourne un code non nul, puisque toutes les preuves restent manquantes.
- La validation de métadonnées n'est pas une preuve cryptographique d'origine ni une qualification opérationnelle. Aucune transition ITIL ni action LIVE ne peut être déduite de ces vues.
