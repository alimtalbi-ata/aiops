# 2026-10-28 19:18 Europe/Paris — P0 Core/Policy DEMO, observation sans effet

## Sources et coordination

- `main` HEAD vérifié avant branche et modifications : `793a5a03688dcb7c1a689d07e31bea770da4bd4f` (PR #136, Chromium Explore/Story). Branche dédiée `feat/p0-demo-core-policy-observation-20261028-1914`, [PR draft #144](https://github.com/alimtalbi-ata/aiops/pull/144). Aucune modification de `main` ni des branches tierces.
- PR ouvertes et travaux voisins lus : #137 (Story HITL read-only), #133 (événements ACME canoniques), #139 (trace NOC), #127/#128 (Explore/Evidence), #49→#106 (pile HITL), #36 (réemploi historique). Continuité, derniers journaux Explore/Story et Worker, `quality.yml`, Core/Policy/Worker et schéma SQL consultés.
- État Debian communiqué par l'utilisateur **non revérifié** : 7 runs DEMO, 5 BLOCKED, 1 RESOLVED avec gate PASS/SIMULATE, 1 RUNNING ancien. Aucun appel Debian, aucune lecture de ces sept runs et aucune extrapolation Payments/E2E.

## Une livraison verticale

- `app/shared/demo_policy_gate_read_model.py` : validation stricte du tuple Run/incident/gate, scope tenant refusé, mode DEMO synthétique uniquement, projection de codes de lecture sans prétendre à une causalité ou à un effet LIVE.
- `app/core/main.py` : nouveau `GET /api/noc/runs/{rid}/policy-status`, réemploi du Bearer interne NOC, jointure SQL atomique `runs` + `incidents` + gate `POLICY`, réponse bornée et `no-store`. Aucune écriture ni commande.
- `tests/test_core_demo_policy_real_integration.py` : tests HTTP/Core/PostgreSQL éphémères pour BLOCKED sans gate, RESOLVED PASS/SIMULATE, RUNNING, gate UNKNOWN, gate falsifiée, LIVE, incident non synthétique, tenant ambigu, auth invalide et Run absent. Fixtures CI propres, **pas** les données Debian.
- `.github/workflows/quality.yml` : une étape dans le job Core/PostgreSQL réel existant ; aucun pipeline créé.
- `docs/demo/ACME-CORE-POLICY-OBSERVATION-V1.md` : contrat et handoff vers Story/HITL ; ce journal.
- Commits : `ee76c096924639b1ac93841e8ba40525dc3ce27e` (read-model), `42499f8efed6dd6a9ff9fa56426dfb75cc9d1aaa` (Core HTTP), `5fafcb418052198a96ff3d56d9bd595e1f7a34b4` (tests), `a95c985ab2ec942f8ba173f0b71e119fdb34f240` (CI), `ec1bea6cc344a318f29f811bfe3ba79bdd4585ec` (contrat). SHA final après ce journal : à vérifier via GitHub.

## Contrat, résultats, risques

- Réponse `aiops.core-demo-policy-observation.v1` : mêmes `run_id`/`incident_id` que Core ; `policy_gate_state=MISSING` en absence de ligne ; `PASS/SIMULATE` n'atteste que la **disposition persistée**, jamais une remédiation. `RUNNING_NO_TERMINAL_PROOF` n'est pas un diagnostic de timeout.
- Indicateurs d'attestation, HITL, Temporal, postchecks, rollback, ACL tenant et LIVE explicitement `false`. Une gate DEMO `PASS/ALLOW` ou un scope tenant non qualifié provoque HTTP 503. L'API exige le Bearer interne et n'est **pas** accessible directement à un viewer.
- Tests locaux : **NOT_TESTED** (accès réseau GitHub indisponible depuis l'environnement local). CI sur la branche/PR : **en attente de résultat vérifié**, ne pas annoncer PASS. Les jobs Core/PostgreSQL et Grafana sont indépendants du parcours complet.
- **NOT_TESTED / BLOCKED** : les 7 vrais Runs Debian, Policy HTTP réelle dans le parcours, Temporal/HITL authentifié, isolation tenant runtime, postchecks/rollback, GLPI/Twin/Payments observés, navigateur Story lié à ce nouvel endpoint, captures/vidéo et NGX/Ollama.
- Risque résiduel : le token de service n'est pas une ACL tenant ; ne pas brancher cette route à un navigateur. Une gate enregistrée peut être stale et ne constitue pas une preuve cryptographique ou une exécution Temporal. Rollback : fermer la PR, aucun schéma ni état Core modifié.

## Prochain micro-lot

Qualifier un lecteur portail sous identité viewer et ACL tenant réelles, puis joindre **explicitement** les IDs du scénario #133/#137 aux Runs Core observés ; afficher `MISSING`, `SIMULATE` et `RUNNING_NO_TERMINAL_PROOF` sans transformer les états synthétiques en preuves LIVE. Ensuite tester HITL/Temporal/postchecks sur services CI éphémères.
