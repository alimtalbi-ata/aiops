# 2026-10-28 23:25 Europe/Paris — P0 NOC/Copilot — future Evidence timestamp fence

## Baseline et coordination
- `main` HEAD vérifié avant modification : `13c455256f34e5e0f0ac55146326888b0fb84c42` (Core/Policy #160). HEAD #162 vérifié : `ec0b72d998ea50948c9aa78c020e9f7d564eabf2`. Nouvelle branche indépendante `test/p0-ledger-evidence-time-fence-20261028-2325` à partir de ce SHA ; PR draft [#167](https://github.com/alimtalbi-ata/aiops/pull/167) empilée sur #162, elle-même dépendante de #161 → #154 → #149 → #145. Aucun merge massif ni modification d'une branche tierce.
- PR ouvertes et branches récentes consultées, dont #140–#146, #153/#156 (Recette), #159/#165 (Twin), #163 (Policy), #166 (UI), #161/#162 (Evidence). Journaux #154, #161 et #162 et contrats Evidence Core/Portal consultés. Les autres propriétaires modifient les mêmes lignées ; ne pas rebâser/forcer sans coordination.
- Une seule livraison verticale : ne pas présenter comme sourcée une Evidence synthétique dont `known_at` se situe dans le futur, même si Analysis/Critique et les liens d'événement sont cohérents.

## Code, tests et contrats
- `10f5bc245316804e69b5fc9723b8a55c90b52f65` — `app/core/demo_evidence_read.py` : vérifie timestamp aware et refuse `known_at` plus de 5 min après l'horloge Core, HTTP 503 fail-closed.
- `ce0497370b4c27299ac2672df16c05a021f25b0d` — `app/portal/demo_ledger_read.py` : second contrôle indépendant avant projection viewer, 503 `UNKNOWN` et `no-store`.
- `2431bf40da79a4a432ea60246b7852fa89a90d4a` — `tests/test_demo_ledger_read.py` : cas négatif `known_at` futur dans la suite unit-only existante.
- `5ec1de2aa5f3cd68a2b4d949004413bc717f0645` — première version du test HTTP réel Core/Portal/PostgreSQL, **échec de setup** : UPDATE interdit par trigger append-only PostgreSQL. [quality #40780155519](https://github.com/alimtalbi-ata/aiops/actions/runs/40780155519), job `database-migrations` FAIL : 9/10 tests HTTP OK, `psycopg.errors.RaiseException: append-only record`. Aucun PASS revendiqué pour cette version.
- `9804a9a52b4928cae94d5902761503ed5219eb7e` — correction du même micro-lot : insertion d'un nouveau Run/Evidence/Analysis/Critique avec `known_at` futur dans PostgreSQL CI **sans UPDATE ni contournement du trigger append-only** ; vérifie Core 503 et Portal 503 UNKNOWN sans fuite. Pas de suppression ni mutation LIVE.
- `d18abcbb4e83c289544c8be7db831dafd94a4952` et `5e3f8f9c1330bf831241c5fa5881f80d98d36136` — contrats `docs/demo/ACME-CORE-LEDGER-EVIDENCE-REFS-V1.md` et `docs/demo/ACME-PORTAL-LEDGER-EVIDENCE-REFS-V1.md` mis à jour.
- Le présent journal est commité sur la même PR ; consulter le HEAD exact #167. Contrats HTTP `aiops.core-demo-evidence-refs.v1` et `aiops.demo-ledger-read.v1` **inchangés en structure**, sémantique fail-closed durcie : 5 minutes de tolérance de dérive, sans garantie d'authenticité ni de fraîcheur. 401 viewer/Core et isolation tenant non qualifiée inchangés.

## Qualification et état de livraison
- Workflow réutilisé : `.github/workflows/quality.yml` de la branche #162 ; aucune CI parallèle créée ou lancée manuellement. [quality #40780155519](https://github.com/alimtalbi-ata/aiops/actions/runs/40780155519) sur première version code/test : compilation et 13/13 tests unitaires Ledger OK, 11/15 tests Policy hérités FAIL, HTTP réel 9/10 avec erreur append-only corrigée au commit `9804a9a`. **Résultat sur SHA corrigé et HEAD documentaire : PENDING à cette mise à jour** ; ne déclarer aucun PASS avant vérification des jobs et logs GitHub.
- Tests locaux : **NOT_TESTED** (pas de clone/accès PostgreSQL local). Les tests unitaires utilisent des objets synthétiques ; le test HTTP ajouté est destiné au vrai Core/Portal/PostgreSQL éphémères de la CI existante.
- Blocages hérités documentés par #162 : Policy safety (11 échecs), Temporal runtime E2E et qualification UI V2.8. La CI verte de sous-étapes ne suffit pas à autoriser fusion/promotion. Un SHA unique convergé est encore absent.
- **NO-GO / READY_FOR_STABLE=BLOCKED** : déployeur Studio V2 ne transporte pas `app/core/demo_evidence_read.py` ni ses dépendances ; Core/Portal doivent être promus ensemble, avec rollback et recette 5/5. Aucun push `deploy/aiops2-stable`, SSH Debian, accès portail, commande LIVE, secrets production, NGX ou preuve `applied.sha`.
- **NOT_TESTED** : identité tenant A/B authentifiée, métriques SAN/Payments observées, causalité Twin runtime, IA Ollama 4B, Policy SIMULATE E2E, screenshots authentifiés, vidéo, smoke-test Debian et rollback.

## Prochain micro-lot et transfert
- Remettre PR #167 + ses checks exacts à la Recette #156, puis converger #145 → #149 → #154 → #161 → #162 → #167 sur un SHA unique après résolution des échecs Policy/Temporal avec leurs propriétaires. Vérifier couverture du déployeur et smoke read-only avant toute décision de stable.
- Le contrôle temporel ne prouve **ni impact Payments ni diagnostic IA réel** ; ne pas remplacer UNKNOWN par une valeur synthétique non attestée.

## Qualification GitHub Actions sur SHA corrigé (2026-10-28 23:30 CET)
- HEAD de code+tests+journal avant ce complément : `4d70ee107f7f74039c17d66152482d741f521613`.
- [`quality.yml` #40780356746](https://github.com/alimtalbi-ata/aiops/actions/runs/40780356746) : **completed/failure**, pas de GO. Job `database-migrations` **SUCCESS** ; logs lus : **10/10 tests HTTP Core/Portal/PostgreSQL 16 OK**, y compris `test_future_dated_evidence_refused_by_real_core_and_portal`. `quality-build-package` **FAIL** après compilation et **13/13 tests unitaires Ledger OK**, puis **11 échecs Policy/15**. `runtime-e2e` **FAIL** sur Temporal synthétique ; `release-kit` SKIPPED. `migration-runner-upgrade` et `mariadb-dr-rehearsal` SUCCESS.
- Sur ce même SHA, [V2.8 #40780356745](https://github.com/alimtalbi-ata/aiops/actions/runs/40780356745) **FAIL** ; [Offline Integrity #40780356693](https://github.com/alimtalbi-ata/aiops/actions/runs/40780356693) et [Historical Trace #40780356770](https://github.com/alimtalbi-ata/aiops/actions/runs/40780356770) **SUCCESS**, sans qualification E2E.
- **La présente mise à jour documentaire crée un nouveau SHA : ses checks doivent être revérifiés séparément.** La CI globale reste rouge, PR #167 draft, **READY_FOR_STABLE=BLOCKED / NO-GO**.
