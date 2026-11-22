# AIOps V3 — Chantier de convergence sélective (registre CENTRAL)

**Ouverture : 2026-11-21** · **Statut : DRAFT / DOCUMENTATION + ARCHIVAGE DE CONTRAT UNIQUEMENT** · **Cible de comparaison : `feature/mission-control-central-unified`** · **Aucune autorisation de fusion ou de déploiement**.

## Mission et limites

Préserver, comparer et intégrer progressivement les fonctionnalités utiles au produit AIOps V3 développées par cinq schedules ChatGPT. Le dépôt `aiops` contient plusieurs centaines de PR depuis #1 jusqu'à #830, des branches historiques V145, des branches de convergence récentes et des dépôts satellites. **Ne pas fusionner toutes les PR** : cela importerait des changements obsolètes, des implémentations redondantes, des contrats incompatibles et des fonctions non qualifiées.

Cette première PR est un **chantier de préparation effectif** : deux fichiers source de la PR #824 sont copiés à l'identique en archives non exécutables sous `docs/convergence/v3/source-imports/`. Ce sont un schéma JSON du parcours Run Journey et une fixture synthétique. Ils ne sont pas branchés dans le portail ni dans les tests de production. Le `$id` du schéma demeure son identifiant historique ; ne pas interpréter son chemin comme preuve de présence sur `main`. **Aucune fonctionnalité runtime n'est intégrée à ce stade.**

## 1. Architecture cible

```text
Portail V3 unique / NOC / Explore / Story / Incident Workbench
       │ authentification OIDC, tenant/actor, projections bornées
       ▼
Core canonique : Event → Incident → Run → Evidence → Policy/HITL
       ├─ Twin : graphe causal sourcé, impact SAN→stockage→Payments
       ├─ Intelligence : Analyst → Critic → citations Evidence (pas d'autorité)
       ├─ Temporal / Worker : activités, idempotence, reprise, reçus durables
       └─ GLPI / NOC / Prometheus / Grafana : adaptateurs read-only qualifiés
       ▼
Déploiement Debian contrôlé : exact SHA, tests, backup, rollback
```

**Invariants :** aucune action LIVE par défaut ; aucune promotion d'un état UNKNOWN à VERIFIED sans preuve indépendante ; aucune corrélation inter-tenant ; pas de double Core/Policy/Run engine ; pas de création de ticket ou d'effet via démo ; provenance et horodatage contrôlés ; CI GitHub et preuve Debian distinctes.

## 2. Matrice priorisée des fonctionnalités candidates

| Priorité | Lot | PR/branches sources à examiner | Objectif | État initial | Gate |
|---|---|---|---|---|---|
| P0 | Autorité Core/Policy/HITL | #5 #49 #76 #118 #194 #239 #466 #470 #478 ; #466–#517 | Reçus idempotents, contrôle d'exécution, séparation des effets | À comparer au code cible | Tests de rejeu, races, tenant, deny LIVE |
| P0 | Identité et sécurité du portail | #69–#126 #229–#335 #518–#665 | OIDC/GLPI actor, ACL, anti-stale, UNKNOWN | Héritage partiellement intégré, delta non vérifié | 401/403/timeout, anti-fuite, multi-tenant |
| P0 | Corrélation et Evidence | #127 #133 #320 #337 #713 #782 #799 | Source→Incident→Run et preuves cohérentes | Candidats isolés | Contradiction, fraîcheur, namespace, replay |
| P1 | Twin et blast radius | #77 #142 #148 #366 #715 #812 #826–#828 | SAN→stockage→Payments explicable | Variantes concurrentes | Arêtes sourcées, sens, UNKNOWN, same-origin |
| P1 | Parcours Run Journey | #792 #813 #818 #824 #825 | Contrat 17 étapes, DEMO vs sandbox | **Schéma + fixture #824 copiés en archive** | Pas de PASS ni d'exécution fictifs |
| P1 | UX NOC/Portal V3 | #131 #385–#416 #629 #714 #771 #809–#811 #821–#823 #830 | Portail unique, recherche Run, cockpit et démonstration | Candidats multiples | Navigation, a11y, Playwright, auth |
| P1 | Analyst/Critic et RAG | #40 #54 #154 #162 #196 #215 #726 #732 #768 #790 | Diagnostic sourcé et critique indépendante | Qualité/autorité à prouver | Citations Core, abstention, coût, latence |
| P1 | GLPI/ITSM | #192 #193 #229 #454 #520 #710 #712 | Inbox HITL, ticket/Run, read-only | Authority gap connu | Entité/tenant/actor GLPI native |
| P1 | Release/DR/QA | #190 #243–#340 #367 #403 #549 #792 #802 #805 #808 #823 #829 | PG16/Temporal, Debian, Playwright, rollback | Tests historiques non transférables | SHA exact + hôte + DR |
| P2 | Observabilité avancée | #187 #196 et dépôts observability-stack/holmesgpt | Traces, métriques, télémétrie IA | HOLD ressources/sécurité | Rétention, ACL, coûts |
| P2 | Patrimoine V145/GAMMA | V145 D4.54–D4.61 ; AIOPS_GAMMA #10–#12 | Fusion de preuves, cockpit décisionnel | Non qualifié / GAMMA NO-GO | Fonctions pures, RLS réel, pas de doublon |

### Candidats déjà avancés à qualifier en premier

- **#818** : candidat de convergence ABC INT-07, 92 fichiers modifiés selon métadonnées GitHub ; la description rapporte 117 tests et 150 subtests mais indique que les preuves historiques/UX restent en attente. **Ne pas fusionner en bloc**.
- **#713** : base de scénario SAN→Payments et gates synthétiques, à comparer à #818.
- **#792** : kit portable + Golden Demo ; inspecter manifeste, scripts et rollback.
- **#824/#825** : Run Journey lié au cockpit existant, sans création de nouvelle route ; schéma et fixture archivés dans cette PR.
- **#809–#811, #821–#828** : convergences UX/Twin/QA ; vérifier l'ordre de base et choisir la variante finale sans triple port.
- **#518–#665** : protections UX, lecture, transport et accessibilité ; éviter toute régression lors d'un redesign.

### HOLD / exclusions temporaires

- **#185** : très grande branche historique divergente ; extraction ciblée seulement.
- **#146/#153/#217** : auto-déploiement sans autorisation/qualification suffisante ; pas de promotion automatique.
- **#187** : Loki/Tempo/OTel sous réserve de ressources, sécurité et rétention.
- **#177** : UI étendue non sûre à fusionner en bloc.
- **#806** : pipeline capture supersédé ; préférer Playwright existant.
- **AIOPS_GAMMA #12** : NO-GO explicite, notamment RLS PostgreSQL non prouvé.
- **#830** : walkthrough statique 5 minutes, **pas** preuve de runtime.

## 3. Inventaire transversal des dépôts

| Dépôt | Usage potentiel | Limite |
|---|---|---|
| `alimtalbi-ata/aiops` | Core/Portal/Twin/Worker, PR historiques et V3 | Référence centrale ; nombreuses branches divergentes |
| `alimtalbi-ata/AIOPS_GAMMA` | UX cockpit, Signal Explorer, Incident Workbench | RLS/autorité non qualifiées |
| `alimtalbi-ata/aiops-debian-audit` | Inventaire read-only, dumps, provenance | Pas une release |
| `alimtalbi-ata/aiops-debian-rebuild-private` | Reconstruction et récupération | PR draft |
| `alimtalbi-ata/aiops-recovery-data` | Sources de récupération | Contenu à inspecter avant usage |
| `observability-stack`, `holmesgpt`, `incidentfox-sre`, `aurora` | Inspirations/possibles adaptateurs | Aucun statut de compatibilité ou de licence validé ici |

## 4. Protocole d'import sélectif — obligatoire pour chaque fonctionnalité

1. **Inventorier** toutes les PR (open, closed, merged, draft), y compris hors main, avec pagination/segmentation. Ajouter dépôt, branche, base/head SHA, CI exact-head, état de review et liens.
2. **Comparer les fichiers réels** à la branche CENTRAL cible ; classer `ALREADY_PRESENT`, `PORT_SELECTIVELY`, `NEEDS_REWORK`, `SUPERSEDED`, `HOLD`. Un titre de PR n'est pas une preuve.
3. **Définir le contrat canonique** : identité source/tenant, schéma, champs de provenance, fraîcheur, types UNKNOWN/ERROR/EMPTY, effets autorisés, ownership Core.
4. **Porter une unité cohérente** (schéma, code, tests, docs, migrations si nécessaires) en commit distinct et traçable ; mentionner PR et SHA sources ; éviter le copier-coller de modules couplés sans leurs dépendances.
5. **Exécuter les gates** : tests unitaires et adversariaux, intégration Core/PG16/Temporal, Chromium Playwright, exact-head CI, puis qualification hôte Debian distincte. Aucune déclaration de PASS sans exécution.
6. **Faire relire par CENTRAL**, documenter rollback, protéger les services existants ; pas de merge, déploiement ni LIVE automatique.

## 5. Répartition entre les cinq schedules

| Responsable | Lot | Livrable requis |
|---|---|---|
| CENTRAL | Architecture, arbitrage, SHA, merge gates | Registre exhaustif et décision par fonctionnalité |
| Équipe A | UX/NOC/Portal | Portail unique, comparaison #401/#714/#809/#822, a11y et tests navigateur |
| Équipe B | Twin/corrélation | Graphe sourcé, identité tenant, provenance, UNKNOWN, sélection #826–#828 |
| Équipe C | Run Journey/Intelligence/ITSM | Contrat #824/#825, Evidence, Analyst/Critic, Policy/HITL, GLPI read-only |
| Équipe D | QA/ops/release | Matrice négative, exact SHA, Playwright, PG16/Temporal DR, Debian rollback |

**Important :** cette attribution est une proposition documentée ; ce commit ne déclenche pas les schedules et ne modifie pas leur configuration.

## 6. Fichiers effectivement copiés dans cette PR

| Destination | Origine | Nature |
|---|---|---|
| `docs/convergence/v3/source-imports/team-c-san-payments-run-journey.schema.json` | PR #824, branche `team-c/san-payments-intelligence-20261119`, blob `d283d615244a868f747b9428bd543e37701ae948` | Copie byte-for-byte du schéma ; pas de chargement runtime |
| `docs/convergence/v3/source-imports/team-c-run-journey.synthetic.json` | PR #824, même branche, blob `605dc6595ebc56a49dbde138540b543ad89b6313` | Fixture synthétique ; aucun Run réel |

**Ne pas utiliser les fichiers importés comme contrats actifs avant revue du schéma et validation de l'implémentation correspondante.** Les chemins ont été changés pour l'archivage, le contenu non.

## 7. Critères de sortie / décision CENTRAL

- [ ] Branche V3 canonique, port d'entrée et interfaces Core/Portal/Twin approuvés.
- [ ] Inventaire exhaustif des PR et branches par dépôt avec SHA et supersessions.
- [ ] Matrice `feature × PR × SHA × status × test × décision` publiée.
- [ ] Deltas #818/#713/#792/#824/#825/#809–#828 examinés au niveau diff.
- [ ] Contrats Core/Run/Twin/GLPI/Intelligence convergés sans doublon.
- [ ] Tests négatifs tenant, replay, stale, provenance, no-LIVE validés sur SHA exact.
- [ ] Tests UX et CI exact-head ; qualification Debian et rollback distincts.
- [ ] Décision CENTRAL écrite : GO ciblé ou HOLD motivé par lot.

**Conclusion :** ce chantier démarre volontairement par un registre détaillé et deux artefacts réels de #824, afin de conserver la traçabilité et éviter de casser le système. La copie du reste des fonctionnalités sera conditionnée à la comparaison des diffs, à la compatibilité des contrats et aux gates de sécurité. **État de livraison actuel : documentation + deux fichiers source archivés ; zéro fonctionnalité runtime intégrée.**
