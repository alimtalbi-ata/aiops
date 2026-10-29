# AIOps2 — Reprise de projet et priorité DEMO ACME (2026-10-29)

> **À lire avant toute nouvelle action.** Ce document est le relais opérationnel entre sessions. Il ne remplace pas les archives historiques, les décisions ni les preuves de CI. Réviser la source et les résultats réels avant toute affirmation.

## Mission produit, non négociable
AIOps2 doit démontrer une IA d'exploitation d'entreprise qui reçoit un incident du **simulateur ACME**, corrèle logs, métriques, topologie, traces et historique, identifie et justifie une cause racine, propose une remédiation, **simule cette remédiation** avec état avant/après, préconditions, échec et rollback, valide le risque via Critic et Policy, documente le ticket, échange avec équipes infra/admin/pilotage/utilisateurs et répond aux questions dans les limites du contexte et des autorisations de l'entreprise. Les tests **Smoke, Chaos et adversariaux** doivent qualifier ce parcours de bout en bout, sans effets sur l'infrastructure réelle.

**Priorité : une démo reproductible et honnête.** Ne pas réinventer les fonctions ACME, portail, simulations, ticketing ou IA déjà développées dans les lignes historiques. Comparer GitHub, branches, ancien worktree, conteneurs et contrats avant de coder.

## Point de reprise vérifié
- GitHub `alimtalbi-ata/aiops`, Debian `SRV-DEB-05`, worktree consolidé `/home/aiops/aiops2-p0-consolidation`, historique local distinct `/home/aiops/aiops-v28-demo`.
- Branche `feat/p0-runtime-consolidated-20261029` commit `321fd5a` **push confirmé** par terminal le 2026-10-29 : 9 fichiers, 570 insertions/15 suppressions. Récupération de protections runtime P0 dans Core/Twin/Policy/Worker/Evidence, deux modules `demo_evidence_read.py` et `tenant_scope.py`, et tests Policy/Twin.
- **18 tests isolés PASS rapportés sur Debian : 11 Policy + 7 Twin**. Les 7 Twin incluent un fake DB qui inspecte la forme SQL, **pas** une traversée PostgreSQL réelle. Compilation du Worker et `git diff --check` réussis. Pas de qualification E2E de cette consolidation.
- Contrat Worker corrigé : DEMO/REPLAY/STORY envoie `command=OBSERVE` à Policy, LIVE reste `EXECUTE`. Policy peut répondre `PASS/SIMULATE` avec Critic validé, preuves fraîches, sévérité connue et confiance >= 0.90 ; **cela ne prouve pas qu'une remédiation a été simulée**.
- Protections : Policy LIVE refuse encore les effets réels ; provenance synthétique `observed=False`, `observed_at=None` ; Twin impact authentifié et décrit comme topologie hypothétique ; Core evidence read refuse de qualifier un ACL tenant réel. Ne pas relâcher ces gardes pour la démo.
- Branche de préparation `prep/acme-demo-offline-20261029` créée sur GitHub à partir de `321fd5a`, avec `tools/acme_offline_source_preflight.py` et `docs/demo/ACME-DEMO-DEPLOYMENT-GATES-20261029.md` ; dernier commit à la création des deux fichiers `0274765`. **Les contrôles de cette branche n'ont pas encore été exécutés sur Debian**.
- `git fetch origin refs/heads/prep/acme-demo-offline-20261029:refs/remotes/origin/prep/acme-demo-offline-20261029` a réussi, puis `git switch -c ... --track origin/...` a échoué car le ref distant explicite n'est pas reconnu comme branche de suivi par la configuration locale. La session SSH a été fermée. **Rien n'indique une perte de fichiers**. Utiliser `git switch -c prep/acme-demo-offline-20261029 refs/remotes/origin/prep/acme-demo-offline-20261029` sans `--track` ; vérifier la branche et la propreté avant de continuer.
- Worktree original `aiops-v28-demo` contient des changements et fichiers non suivis, dont `app/portal/demo_v2.py` et des tests ; **ils ne sont pas automatiquement dans GitHub**. Ne pas écraser ni ajouter sans examen et audit de secrets.
- Les conteneurs `aiops2-rebuild-*` tournent sur Debian (état à revalider). Cinq endpoints Prometheus étaient DOWN (Content-Type/404) ; correctifs source dans la consolidation **non déployés**. Grafana historique/portail et dashboard à requalifier. Aucun redémarrage Docker n'a été effectué pour cette consolidation.

## Historique important à ne pas effacer
- `docs/PROJECT-CONTINUITY.md` et `docs/RECONSTRUCTION-EXECUTION-PLAN.md` racontent l'architecture et le travail antérieur, mais le premier était daté 2026-10-20 avant cette reprise.
- `docs/ACME-DEMO-RUNBOOK-V2114.md` décrit une démo historique avec `/acme-stories`, `/timeline`, `/policy-story`, `/qualification-lab`, `/copilot` et des tests historiques du 21 octobre ; ne pas les présenter comme des tests courants.
- `docs/PROJECT-CONTINUITY.md` rapporte une CI du 20 octobre PASS sur un environnement jetable avec un run Temporal synthétique, un Analyst/Critic déterministe et zéro effet. **Ce n'est pas la validation de la consolidation du 29 octobre ni une qualification LLM réelle**.
- `app/portal/qualification_lab.py` expose des prévisualisations `simple/complex/chaos/smoke_screen` en lecture seule ; ne pas confondre avec chaos réel.
- `app/simulator/main.py` lance DEMO/REPLAY/STORY via Core ; `app/worker/main.py` injecte des preuves synthétiques SAN, appelle Analyst/Critic et Policy ; `app/core/main.py` contient propositions de remédiation. Le moteur complet de simulation de remédiation, sa traçabilité, les tickets GLPI et les interactions de rôle doivent encore être **retrouvés dans l'ensemble des branches et qualifiés** avant de les déclarer manquants.
- `tests/runtime-e2e.sh` est couplé à un Compose/DB précis ; ne pas le lancer à l'aveugle sur le stack existant.
- `deploy/install-isolated.sh` est conçu pour un environnement séparé, mais **le stack cible `aiops2-rebuild` existe déjà**. Ne pas exécuter l'installateur sans vérification d'identité, volumes, migrations, ports et rollback.

## Matrice d'état (à enrichir avec preuves)
| Fonction | Source identifiée | Test actuel | État honnête |
|---|---|---|---|
| Simulateur ACME et injection | simulator/Worker | source inspectée | E2E à refaire |
| Logs/metrics/topologie | Worker/Twin/Evidence | Twin 7 isolés | intégration à qualifier |
| Analyst + Critic | Intelligence/Worker | CI historique | modèle réel à qualifier |
| Policy et refus LIVE | Policy | 11 isolés | source P0 prête, pas déployée |
| Proposition remédiation | Core | source inspectée | flux à qualifier |
| **Simulation remédiation avant/après** | à retrouver dans historique | aucune preuve actuelle | **priorité P1** |
| Chaos/Smoke | qualification_lab + autres à inventorier | prévisualisation identifiée | campagnes E2E à qualifier |
| GLPI/n8n, communication | intégrations historiques | non vérifié | à qualifier |
| Copilot entreprise/RAG/RBAC | services historiques | non vérifié | à qualifier |
| Portail, Grafana, Prometheus | sources et conteneurs | métriques en défaut observé | à corriger et revalider |
| Reproductibilité Docker/CI | install-isolated, Compose, tests | CI historique | staging neuf à qualifier |

## Ordre de travail obligatoire
1. **Audit historique large AVANT nouvelles fonctions** : lire README et continuité, architecture, décisions, catalogue réutilisation, qualification, branches/PR/commits, `docs/`, `app/`, `tests/`, `tools/`, `deploy/` ; inventorier simulateur, scénarios, chaos, smoke, remediation, tickets, Copilot, RAG, portails et observabilité. Distinguer absent de non encore trouvé.
2. Consolider un **catalogue de capacités** avec fichiers/branches, interfaces, état réel, tests, dépendances et lacunes ; prioriser un seul scénario ACME SAN/Payments.
3. Écrire tests isolés et E2E d'une **simulation de remédiation** traçable (avant/après, échec, rollback) sans aucun effet réel. Qualifier l'IA sur les preuves synthétiques ; ne jamais inventer de root cause.
4. Préparer une release candidate avec Compose/images reproductibles, CI, preuves, migrations, secrets, ports, backups/rollback, rapport et kit offline.
5. **Après acceptation uniquement**, fournir à l'opérateur la commande Bash de déploiement isolé sur Debian, puis valider la démo de bout en bout.

## Format de compte rendu pour chaque session
Ajouter dans GitHub : date, branche et SHA, objectif DEMO, découvertes (chemins/contrats), fichiers changés, commandes réellement exécutées et résultats, limites/non exécuté, risques et décisions, liens PR/CI, état Docker réel si vérifié, **prochaine commande unique** et conditions GO/NO-GO. Ne pas transformer une hypothèse en succès. Ne pas divulguer secrets ou données internes dans les documents publics.

## Consigne de reprise à l'assistant
**Ne jamais perdre le fil** : l'objectif est le parcours ACME incident → IA RCA → simulation remédiation → décision → ticket/communication → UI. Lire ce document et les dossiers historiques avant de recommander de nouvelles implémentations ou un déploiement. Préparer le maximum directement dans une branche GitHub ; demander à Debian uniquement les vérifications ou actions qui nécessitent réellement l'hôte. 


## Mise à jour vérifiée — 2026-10-29, Debian 26/26 et synchronisation Git

**Journal détaillé : [JOURNAL-QUALIFICATION-2026-10-29.md](demo/JOURNAL-QUALIFICATION-2026-10-29.md).** L'opérateur a confirmé :
- `git switch -c prep/acme-demo-offline-20261029 refs/remotes/origin/prep/acme-demo-offline-20261029` réussi au SHA `0274765` ; aucune nécessité de `--track`.
- `python3 tools/acme_offline_source_preflight.py` : **26 PASS / 0 FAIL** (11 sources Python, 15 motifs/contrats). **Statique uniquement** ; pas de tests Docker, DB, Temporal, IA réelle, remédiation simulée ou GLPI.
- `git fetch` explicite et `git merge --ff-only` : `0274765..adbdc30`, ajout de deux documents, 63 lignes ; `git status --short` vide. Debian était au SHA `adbdc30` au moment de cette vérification.
- Le présent journal a été publié **après** cette synchronisation et rendra Debian momentanément en retard sur GitHub ; nouvelle synchronisation nécessaire avant de prétendre à l'alignement.
- **Prochaine priorité :** inventaire historique transversal des branches, anciens composants et fichiers locaux non suivis, puis qualification de la simulation de remédiation. Ne pas déployer la consolidation sur `aiops2-rebuild` à ce stade.


## Incrément de code — 2026-10-29 : labo de remédiation historique réutilisé

**Voir [l'implémentation et ses tests](demo/IMPLEMENTATION-REMEDIATION-2026-10-29.md)** et [l'inventaire historique](demo/INVENTAIRE-HISTORIQUE-GITHUB-2026-10-29.md). Le labo no-effect a été retrouvé dans `feat/p0-hitl-remediation-lab-simulator-20261027-2024` puis porté dans la branche prep : `app/shared/remediation_lab.py`, `config/remediation/recipes.v1.json`, `tests/test_remediation_lab.py`. Un nouveau module `app/shared/acme_remediation_projection.py` et ses tests projettent un état synthétique avant/après et un rollback hypothétique. **Aucun effet réel, aucune postcondition observée, aucune authentification HITL réelle, aucun raccord Core/Temporal/Portal/GLPI pour le moment.** Dernier commit de cette livraison avant cette mise à jour documentaire : `18193a17`. Les tests de ce nouvel incrément **ne sont pas encore exécutés sur Debian** ; demander uniquement les tests Python offline, pas de déploiement Docker.
