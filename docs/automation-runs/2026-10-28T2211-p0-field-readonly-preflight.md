# 2026-10-28 22:11 Europe/Paris — Recette 5/5, sonde terrain locale en lecture seule

## Références vérifiées avant modifications
- `main` HEAD : `ec05c89e92a6611922dccbe3690ce1476e3aec92` ; `deploy/aiops2-stable` HEAD : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`. GitHub compare : `diverged`, 39 commits ahead côté main, 633 behind ; **aucun fast-forward possible**.
- Branche de travail conservée (périmètre Recette 5/5) : `fix/p0-stable-deploy-coverage-20261028-2149`, [PR draft #156](https://github.com/alimtalbi-ata/aiops/pull/156) vers `main`. HEAD de départ PR : `8aea522787d72f67100d26a695c7120c6cddf207`.
- PR et travaux consultés : #140/#142/#143/#144/#145/#146/#152/#153/#154/#155/#156, et travaux Core/Policy, Twin, Demo Studio, NOC. #153 est verte à son SHA `d5243b769035aedf4e66b1416a7cdee83ff2ea24` (Actions) mais **ne transporte que les sources Demo Studio et un fragment de main.py**, pas Core/Twin/Copilot ; la promotion reste bloquée. #146 non mergeable ; autres PR non assemblées ni qualifiées ensemble.
- Documents : `docs/PROJECT-CONTINUITY.md`, `docs/automation-runs/2026-10-28T2110-p1-acme-aggregate-source-fence.md`, journal précédent `2026-10-28T2149-p0-stable-deploy-coverage.md`, `.github/workflows/quality.yml`, déployeur/poller/workflow de #153.
- Risque supplémentaire : `.github/workflows/promote-stable.yml` de #153 propose une PR sur succès CI de `main` et contrôle l'ascendance, mais **ne qualifie pas** couverture des fichiers, smoke terrain, rollback ou E2E. Ne pas interpréter cette proposition comme GO.

## Micro-livraison
- `scripts/check_demo_field_readonly.py` : sonde opérateur **uniquement sur ports loopback explicitement forwardés** (littéraux 127.0.0.1 ou ::1), GET /health de Core/Twin/Copilot/Portal, refus HTTP 401 de la route Core NOC sans jeton, présence de la page `/demo-studio`. Sans POST, secrets, DNS, redirections, proxy ou accès direct à Debian ; réponses limitées à 8192 octets ; reçu JSON horodaté UTC sans corps HTTP ni token.
- `tests/test_demo_field_readonly.py` : neuf tests sur de **vrais serveurs HTTP éphémères de fixture**, et non les vrais services applicatifs. Cas négatifs : mauvais composant, Core anonyme 200/503, redirection, réponse trop grande, service indisponible, destination non loopback, validation globale avant I/O.
- `.github/workflows/quality.yml` : une étape de test ajoutée au job existant, **aucun nouveau workflow**.
- Commits : `4f684771780753234d2a11febf7dcc4c23d65663` (sonde), `3d12dacb80a651e56cb3c70419d0c99be77a33a3` (tests), `1173a0fde4de2e9b3d245f5cb6fa2f6443af0c13` (CI), présent journal (SHA à relever dans PR).

## Contrat et exécution future (opérateur autorisé seulement)
- Contrat nouveau : `aiops.demo-field-readonly-preflight.v1`, `assessment=READONLY_PREFLIGHT_PASS|BLOCKED`, **toujours `overall=NO_GO`**. Provenance `OPERATOR_LOCAL_READONLY_OBSERVATION_UNATTESTED` ; la réussite n'est ni E2E, ni une attestation indépendante de session.
- Exemple **non exécuté sur Debian** : après mise à disposition contrôlée de tunnels/ports **loopback locaux**, depuis un environnement opérateur autorisé :
  `python3 scripts/check_demo_field_readonly.py --core-url http://127.0.0.1:1810 --twin-url http://127.0.0.1:1811 --copilot-url http://127.0.0.1:1814 --portal-url http://127.0.0.1:1777 > field-preflight.json`
- Ne pas configurer de port-forward sur un hôte de production sans autorisation ; ne pas connecter la sonde au poller. Le reçu n'inclut aucun `applied.sha` attesté ; un opérateur devra fournir SHA appliqué, journaux datés et résultats de smoke signés/contrôlés indépendamment.
- Les routes Core GET existantes ne prouvent pas l'isolation tenant ; un HTTP 401 anonyme sur une route NOC ne qualifie pas RBAC. Les métriques Payments, IDs de Run/Incident/Evidence, Policy SIMULATE, Temporal, Analyst/Critic, rollback et E2E restent `NOT_TESTED`.

## Tests réellement exécutés et limites
- Local : `PYTHONPATH=. python -m unittest discover -s tests -p test_demo_field_readonly.py -v` sur fixtures HTTP éphémères : **9/9 OK** ; aucun service Core/Twin/Copilot/Portal réel interrogé.
- CI GitHub Actions du HEAD final : **PENDING** au moment du commit documentaire ; consulter les checks de la PR #156 et consigner l'URL du run/conclusion après vérification. Les checks antérieurs du HEAD `8aea522` étaient verts, **pas une qualification du nouveau code**.
- Terrain Debian / `applied.sha` / E2E interservices / rollback : **NOT_TESTED**. Aucune requête au serveur Debian, aucune promotion stable, aucune mutation LIVE.

## Matrice GO/NO-GO et prochain micro-lot
| Priorité | Critère | Statut |
| --- | --- | --- |
| P0 | Ascendance stable et transport Core/Twin/Copilot | **BLOCKED** : divergence + déployeur limité |
| P0 | CI combinée des PR #140–#155 sur un SHA candidat | **NOT_TESTED** |
| P0 | Recette terrain authentifiée, applied.sha, rollback | **NOT_TESTED** |
| P0 | Corrélation Core→Temporal→Analyst/Critic→Policy SIMULATE→Evidence→Portal | **NOT_TESTED** |
| P0 | Twin SAN→Payments observé | **NO_GO** : seule la topologie est déclarée |
| P1 | Sonde de disponibilité locale et refus anonyme | **PASS sur fixtures HTTP uniquement** ; terrain NOT_TESTED |

**Décision : BLOCKED / NO-GO, pas READY_FOR_STABLE.** Prochain lot : proposer une branche candidate d'assemblage ciblé avec transport explicite des modules Core/Twin/Copilot, puis étendre la recette opérateur aux IDs et reçus Evidence sous auth tenant qualifiée ; exiger CI complète, rollback et preuve terrain avant toute promotion.

## Clôture de la qualification du code et audit supplémentaire
- Correctif de taille HTML bornée (Demo Studio réel potentiellement supérieur à 8 KiB) : `82fbf4bba8acc3c0335fe9fb54a5cab946b5839f` ; test de réponse HTML supérieure à 128 KiB : `7eeddd5fd87519619607f5ba4f28117438843331`.
- Tests locaux réexécutés sur le correctif : **9/9 OK** (vrais serveurs HTTP fixtures, pas services applicatifs).
- CI **SHA code/tests exact `7eeddd5fd87519619607f5ba4f28117438843331`** : [quality.yml PR #40770474397](https://github.com/alimtalbi-ata/aiops/actions/runs/40770474397) et [quality.yml push #40770461545](https://github.com/alimtalbi-ata/aiops/actions/runs/40770461545), tous deux `completed/success` ; **3/3 jobs SUCCESS** chacun (policy-and-static, Core/PostgreSQL éphémère, Grafana éphémère). Logs du job PR lus : **9 tests smoke exécutés, 9 OK**. Les jobs Core/PostgreSQL et Grafana ne qualifient pas le scénario ACME E2E. Après ce commit documentaire, revérifier les checks du HEAD final.
- Revue statique complémentaire de #153 : `deploy/deploy-demo-studio-v2.sh` définit `BACKUP="aiops2-portal-rollback-v2-$(date ...)-$"`, contenant un dollar littéral terminal. Une expansion Bash **réellement exécutée localement** confirme le suffixe `-\$`, qui ne correspond pas au format des noms de conteneur Docker ; **aucun test Docker ni rollback terrain exécuté**. Blocage P0 signalé à la PR #153 ([commentaire](https://github.com/alimtalbi-ata/aiops/pull/153)). Corriger et tester avant toute promotion.
