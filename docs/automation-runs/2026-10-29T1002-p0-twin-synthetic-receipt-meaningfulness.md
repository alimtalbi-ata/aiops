# 2026-10-29 10:02 Europe/Paris — P0 ACME Twin : refus des faux reçus synthétiques

## Sources et coordination (lecture GitHub effective)

- HEAD `main` : `27deb9b1a66faf27df8d69b137a63451f7649d80` ; `deploy/aiops2-stable` : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`, **non modifiés**.
- Candidate ACME unique : [PR #170](https://github.com/alimtalbi-ata/aiops/pull/170), branche `feat/p0-acme-twin-main-candidate-20261029-0004`, base `main`, draft. Pas de nouvelle PR ni de workflow.
- PR source [#142](https://github.com/alimtalbi-ata/aiops/pull/142) (direction inverse) : CI [40744150243](https://github.com/alimtalbi-ata/aiops/actions/runs/40744150243) success sur `e666ce7a875ce7ee2fbdde6b7a2f35abb1f463f5` ; [#148](https://github.com/alimtalbi-ata/aiops/pull/148) (arêtes SQL) : CI [40760838278](https://github.com/alimtalbi-ata/aiops/actions/runs/40760838278) success sur `280166ae1cf1dd475be23ab12c61102706dcdad7`. Les corrections ont déjà été portées sur #170 ; ne pas fusionner la pile historique.
- PR #140, #145 ont des checks en échec ; #146 n'a pas de workflow PR trouvé sur son SHA. #141 fusionnée, #144 fermée non fusionnée, #143 ouverte. Aucune de ces PR n'est réputée prête par héritage.
- Journaux des autres créneaux et [#156 Recette 5/5](https://github.com/alimtalbi-ata/aiops/pull/156) consultés : #156 assemble des reçus de couverture sans attester Debian/E2E ; #176 Worker/Policy, #171 Ledger et #177 UI ne sont pas une chaîne E2E qualifiée.

## UNE livraison verticale : intégrité des reçus `POST /api/twin/synthetic-event`

Source de vérité : `app/twin/main.py` et `app/worker/main.py` (Worker main utilise `SET_STATE` avec `state=DEGRADED, health=0.42` et `OBSERVE` avec `metric=fc_errors, value=184`). Aucun changement aux arêtes ni aux migrations.

Avant correction, un credential administrateur brut dans `Authorization`, un `SET_STATE` sans `state` ou un `OBSERVE` sans mesure numérique pouvaient produire un accusé `PASS` non fiable. Le handler impose désormais :
- exactement `Authorization: Bearer <admin-token>` ; credential brut, Basic ou absent → 401 avec `WWW-Authenticate: Bearer` et `Cache-Control: no-store` ;
- `run_id` et `target_node_id` non blancs, action limitée à `SET_STATE`/`OBSERVE` → 422 sinon ;
- nœud inexistant → **404 conservé**, même si le payload est incomplet ; aucune écriture avant validation ;
- `SET_STATE` : `state` non vide, `health` optionnel mais numérique fini entre 0 et 1 ;
- `OBSERVE` : `metric` non vide et `value` numérique fini, sans booléen ;
- un `PASS` n'est qu'un reçu d'opération **DEMO/SIMULATED**, pas une preuve de panne, de Policy PASS, de remédiation LIVE, de Run canonique ou d'impact Payments.

Le contrat d'impact GET et la topologie synthétique restent inchangés. Le chemin Twin `ACME-SAN-FABRIC-A → ACME-STO-PURE01 → ACME-VM-PAY01 → ACME-APP-ORACLEPAY → ACME-SVC-PAYMENTS → ACME-BIZ-PAYMENTS` est une **hypothèse topologique seed** par `ACME-E08/E06/E04/E02/E01`, pas un impact runtime. Aucune arête SAN→hôte, aucune jointure prouvée avec le fixture Portal, aucune ACL tenant qualifiée.

## Code, tests et checks réellement observés

- Commits : code `b33cff7b959ba8216a0a426a3003d7d937cd008f` ; test `7ed7c98bb806260ffb9a24e55a8f5fd89ddbb91f` ; compatibilité 404 `2663ee2aecf5316357c465c155a1ac1412335416`.
- Test nouveau : `test_admin_synthetic_event_refuses_unbound_payloads_and_bare_auth`, **16 cas négatifs** sur vrai HTTP Twin / PostgreSQL 16 éphémère ; comparaison des compteurs de faits/observations et de l'état SAN avant/après ; aucune mutation attendue.
- Première CI [#40846675736](https://github.com/alimtalbi-ata/aiops/actions/runs/40846675736) **FAILURE** : l'ancien test exigeait 404 pour un nœud inconnu avec payload OBSERVE incomplet, mais la nouvelle validation retournait 422. Ce défaut de compatibilité a été corrigé, sans masquer l'échec.
- CI corrigée [#40846809457](https://github.com/alimtalbi-ata/aiops/actions/runs/40846809457), sur le SHA code/tests `2663ee2aecf5316357c465c155a1ac1412335416` : **3/3 jobs SUCCESS** (Core/PostgreSQL, statique/Policy, Grafana). Logs du job Core : **16/16 tests Twin HTTP réel**, dont nouveau test et ancien 404, **2/2 scrape Prometheus réel**, **14/14 Core/Policy**, **8/8 Policy HTTP**, **5/5 Core NOC**. Aucun workflow CI supplémentaire.
- Tests ciblés locaux : **NOT_TESTED** (pas de clone/Docker local qualifié). Les tests ciblés sont ceux du job existant `quality.yml` ; la CI complète est celle du SHA corrigé. Le commit documentaire postérieur nécessite sa propre vérification de checks, sans héritage automatique.

## Contrats non qualifiés / risques / prochain lot

**READY_FOR_STABLE=BLOCKED ; GO/NO-GO=NO-GO.** Tests positifs Worker→Twin avec Run canonique, RBAC tenant A/B, corrélation Core→IA→Policy SIMULATE→Evidence→Studio, transport multi-services, rollback, `applied.sha`, vrai Prometheus Debian et smoke-tests SRV-DEB-05 : **NOT_TESTED**. L'authentification interservice ne prouve pas l'isolation tenant.

Le déployeur stable connu ne transporte que `demo_v2.py`, `test_demo_v2.py` et une injection de `main.py` ; les changements Twin/Core/Worker ne sont pas automatiquement installés. Le poller vérifie `deploy/aiops2-stable` uniquement, pas cette PR ; il n'atteste aucun E2E. **Aucune promotion, fusion, mutation LIVE, connexion Debian ou écriture stable.**

Handoff requis à **#156 Recette 5/5** : intégrer seulement après CI verte du SHA exact, vérifier transport/rollback et compatibilité Worker, exécuter recette post-déploiement lecture seule et récupérer preuves horodatées `applied.sha` + smoke-tests observés. Si impossible : rester NO-GO.
