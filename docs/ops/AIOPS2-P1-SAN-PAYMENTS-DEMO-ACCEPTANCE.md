# AIOPS2 — démonstration vérifiable du parcours P1 SAN → Payments

**Statut :** scénario ACME synthétique, lecture seule pour les vues de qualification. Aucune preuve de production, aucune remédiation LIVE.

## Proposition de valeur montrée à l'opérateur

Une dégradation SAN affecte le service Payments. La plateforme relie **signal technique → incident P1 → dépendance métier → preuves → hypothèses Analyst/Critic → Policy/HITL → simulation → vérification indépendante → ITIL**. Le point important n'est pas un écran vert : c'est de montrer **pourquoi** une étape est autorisée, refusée ou UNKNOWN, avec identifiants et provenance cohérents.

Le démonstrateur existant est le cockpit synthétique du Portal et ses projections de cycle de vie, de préparation ITIL, de plan de collecte de preuves et de revue Analyst/Critic. Les routes et projections sont documentées dans `docs/customer-story/ACME-P1-SAN-PAYMENTS-ITIL-DEMO-2026-10-30.md`. Ne pas substituer une exécution Temporal réelle à ces projections sans attestation indépendante.

## Parcours de démonstration (8–12 minutes)

| Temps | Montrer | Preuve vérifiable | Ce qu'il ne faut pas affirmer |
|---|---|---|---|
| 0–2 min | Incident P1 SAN → Payments, impact métier et chemin de dépendances | Même incident ID, chemin et `source_sha256` dans les projections | CMDB ou supervision réelles connectées |
| 2–4 min | Contexte des preuves et lacunes | Plan de collecte, sources attendues, `verified_count=0` | Preuves authentifiées par le seul manifeste |
| 4–6 min | Hypothèses Analyst et objections Critic | Citations de fixture, objections, `runtime_citations_verified=0` | Diagnostic IA exécuté sur une production |
| 6–8 min | Policy/HITL et transitions ITIL | `DENY_LIVE_ACTION`, `authorized_transition_count=0` | Autorisation d'une action réelle |
| 8–10 min | Simulation isolée et postcheck | Reçu simulé sans effet réel; vérification indépendante UNKNOWN | Réparation réelle, succès VERIFY, clôture GLPI |
| 10–12 min | Incident/Run et démarrage Temporal, **uniquement si environnement isolé disponible** | Intention Core persistée, inspection Temporal, comparaison `MATCH/MISMATCH/UNKNOWN` | MATCH = exécution réussie ou idempotence attestée |

## Démonstration de la sûreté du démarrage (séparée du scénario métier)

La démonstration de la protection contre les démarrages multiples est **un test d'infrastructure**, pas la preuve que le parcours métier P1 a été exécuté :

1. Sur une base PostgreSQL et un Temporal jetables, créer un run DEMO distinct.
2. Afficher la ligne `aiops.execution_start_intents` (run ID, mode, scénario, version initiale), écrite **avant** l'appel Worker.
3. Simuler une réponse HTTP perdue après acceptation Temporal; constater `503`, sans reçu d'exécution.
4. Rejouer la même requête; constater `409` et **aucun second POST** Worker.
5. Consulter `GET /api/runs/{rid}/execution-inspection`. Présenter `start_arguments_comparison` et `core_start_intent_present`, mais conserver `execution_start_outcome=UNKNOWN`, `idempotent_start_confirmed=false`, `live_remediation_authorized=false`.
6. Présenter les tests de concurrence PostgreSQL : un seul INSERT gagnant, UPDATE/DELETE refusés. La CI doit être verte avant d'annoncer ces résultats.

## Contrat d'acceptation observable

- Le cockpit renvoie `mode=DEMO`, `provenance=LOCAL_SYNTHETIC_FIXTURE`, `runtime_attested=false`, `overall_qualification=UNKNOWN`.
- Toutes les projections partagent le même SHA-256 et les identifiants d'incident; aucune transition ITIL n'est autorisée.
- Les vues Analyst/Critic distinguent hypothèses et preuves; aucune citation runtime n'est qualifiée.
- Le démarrage Temporal est **optionnel et isolé**; une comparaison des paramètres ne transforme jamais une simulation en preuve de récupération.
- Toute pièce absente, incohérente ou non authentifiée apparaît **UNKNOWN/BLOCKED**, jamais PASS.
- Capturer les réponses JSON horodatées, le commit, les logs CI, les IDs et les hashes; ne pas fabriquer de captures ni de preuves.

## Critères de non-démo

Interrompre la démonstration plutôt que masquer une panne si la fixture ne valide plus son hash, si les IDs divergent, si un composant présente un PASS sans preuve indépendante, si la CI est rouge, ou si l'environnement n'est pas explicitement isolé. Aucun merge, déploiement, ticket GLPI écrit, reconciliation ou LIVE n'est nécessaire.


## Dossier de preuve reproductible — contrôle anti-falsification

Générer le dossier depuis le checkout exact de la démonstration :

```bash
python scripts/package_aiops2_demo_evidence.py --output /tmp/aiops2-demo
python scripts/package_aiops2_demo_evidence.py --verify /tmp/aiops2-demo
```

Présenter les quatre fichiers `cockpit.html`, `cockpit.json`,
`acceptance.json` et `manifest.json`. Le vérificateur compare les SHA-256,
les identifiants, les marqueurs de non-qualification et **les octets exacts
régénérés depuis la fixture canonique du checkout**. Recalculer les hashes
après modification du HTML ou du rapport ne permet pas de faire accepter
un contenu différent. Le même checkout de référence doit être conservé
pour une vérification ultérieure.

Cette vérification ne prouve pas l'origine indépendante du dépôt, l'identité
d'un auteur, la présence de sources externes authentifiées, une exécution
Temporal ou un rétablissement réel. Pour une chaîne de confiance hors dépôt,
prévoir un artefact CI signé et une provenance vérifiée séparément.

## Vérification de l'archive GitHub Actions téléchargée

Depuis le checkout **exact de la révision ayant généré le dossier**, lancer :

```bash
python scripts/verify_aiops2_demo_zip.py aiops2-san-payments-synthetic-demo.zip
```

Le contrôle refuse les fichiers ZIP inattendus, les entrées supplémentaires,
les contenus falsifiés et les écarts avec les octets canoniques du scénario.
Il ne décompresse aucune entrée du ZIP sur le système de fichiers cible avant
la vérification de sa liste et de ses tailles; les quatre fichiers attendus
sont copiés dans un répertoire temporaire privé pour comparer à la fixture.
Le résultat PASS est limité au **scénario synthétique**. Le `git_revision`
du manifeste correspond au checkout GitHub Actions (potentiellement un commit
de merge de PR), pas nécessairement au SHA de tête de branche. Ne pas utiliser
ce champ comme signature d'origine.

## Fiche de répétition opérateur (12 minutes, hors production)

Après génération et vérification du dossier canonique :

```bash
python scripts/rehearse_aiops2_customer_demo.py /tmp/aiops2-demo \
  --output /tmp/aiops2-demo-repetition.md
```

La fiche indique les six séquences métier et leurs critères observables,
avec IDs et SHA issus du dossier vérifié. Elle ne fait aucun appel réseau
et ne modifie aucun ticket. Une pièce modifiée ou absente bloque la génération.
L'animateur doit verbaliser les trois résultats séparés : **GO scénario
synthétique**, **NO-GO LIVE**, **UNKNOWN preuves runtime**.
