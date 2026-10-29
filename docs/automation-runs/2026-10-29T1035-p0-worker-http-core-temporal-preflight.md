# 2026-10-29 10:35 Europe/Paris — P0 Worker HTTP réel, Core/PostgreSQL éphémères, Temporal instrumenté

## État relu avant modification
- HEAD `main` GitHub : `27deb9b1a66faf27df8d69b137a63451f7649d80`.
- HEAD `deploy/aiops2-stable` : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`, inchangé.
- Candidate Policy/HITL/Temporal existante : [PR #176](https://github.com/alimtalbi-ata/aiops/pull/176), branche `fix/p0-policy-synthetic-critic-fence-20261029-0235`, HEAD initial `12fad6c153ad252d8772870b2aa4a0c95e4df928`, draft.
- Relecture des PR #140–#147, #155, #163, #156 Recette, #170 Twin, #171 NOC, #177 UI et des journaux Policy 07:35, 08:38, 09:39, ainsi que `quality.yml`, Worker, Core et le déployeur. #144→#147→#155→#163 déjà convergées sur main ; #140/#145 CI rouges historiques ; #146 sans qualification PR démontrée ; #177 UI rouge. #171 NOC change son contrat Policy et le validateur offline de #156 doit être adapté par Recette. Ne pas fusionner ces branches en bloc.
- Observations Debian historiques (non revérifiées) : 7 Runs DEMO, 5 BLOCKED sans gate causal démontré, 1 RESOLVED avec gate PASS/SIMULATE sans remédiation LIVE, 1 RUNNING ancien sans terminaison Temporal attestée. Twin SAN→Payments réel non prouvé.

## Une livraison verticale : authentification Worker et import/runtime HTTP réellement exercés
**Découverte P0 par la CI réelle** : l'import de `worker.main` échouait avec `temporalio==1.17.0` : `RetryPolicy.__init__() got an unexpected keyword argument 'max_interval'`. Les tests AST antérieurs n'avaient pas importé le vrai module Worker. Correction du nom de paramètre en `maximum_interval`, conforme à la dépendance verrouillée dans `app/requirements.txt`. Sans ce correctif, aucun Worker Temporal ne peut démarrer.

- `app/worker/main.py` : refus HTTP 401 des en-têtes `Authorization` multiples, même si l'un contient le Bearer exact ; `Request.headers.getlist` est vérifié **avant** lecture Core ou connexion Temporal. Maintien du Bearer strict déjà introduit. `RetryPolicy(maximum_interval=...)` permet l'import avec Temporal SDK réel.
- `tests/test_worker_http_real_integration.py` : **7 tests** qui démarrent le vrai serveur HTTP Worker sur loopback, lisent le vrai Core HTTP et PostgreSQL 16 éphémères, utilisent des fixtures DB synthétiques isolées, et remplacent uniquement la connexion/dispatch Temporal par un enregistreur sans exécution. Vérifient Bearer absent/nu/ambigu, en-têtes dupliqués sur le fil HTTP, bindings DEMO/LIVE et statuts Core incompatibles, Core 404→Worker 503, requête DEMO valide et absence de mutation Core (Run reste CREATED, zéro gate/event).
- `.github/workflows/quality.yml` : étape dans le job Core/PostgreSQL existant, installation `temporalio==1.17.0` et `PYTHONPATH=app`, aucune création de workflow. Le test refuse de fonctionner hors `AIOPS_REAL_WORKER_HTTP_CI=1` avec PostgreSQL loopback et jeton CI éphémère. Aucun accès Debian.
- Contrat interne resserré : `POST /api/execution/start` refuse les champs Authorization multiples avec 401. La requête DEMO valide retourne seulement un reçu de **dispatch instrumenté**, pas une exécution Temporal. Aucune API Core/Policy/Evidence publique modifiée. L'espace blanc final peut être normalisé par le parseur HTTP ; le test HTTP ne prétend pas observer les octets supprimés, le helper strict reste couvert en unitaire.

## Commits et CI — ne pas recycler des checks d'un ancien SHA
- `61d45fdd603e46ad8695d0bf1a0f2f9ff41f5ce0` : refus des en-têtes multiples.
- `655946c27f2793b4496ff8f837dcbea6086b8b0b` : sept tests Worker HTTP/Core/PostgreSQL avec Temporal instrumenté.
- `4523449fdc34e5f71150e35ecb0b4b65927a2477` : intégration dans `quality.yml` existant.
- `3a2c31158693073ba014ea063d92784335464c87` : correction P0 `RetryPolicy.maximum_interval`.
- `ed1ab823497a8f6879cca102a6ab86069941b8cd` : correction d'une assertion HTTP irréaliste après normalisation de l'espace final.
- [CI #40850577761](https://github.com/alimtalbi-ata/aiops/actions/runs/40850577761) **FAILURE** sur le SHA `4523449f` : véritable import Worker impossible (`max_interval`).
- [CI #40850700222](https://github.com/alimtalbi-ata/aiops/actions/runs/40850700222) **FAILURE** sur le SHA `3a2c3115` : **6/7 tests HTTP PASS**, une assertion négative non représentative du parseur HTTP échoue (OWS final supprimé avant ASGI). L'import et les six cas, dont refus des en-têtes dupliqués, ont été effectivement exécutés.
- **CI du SHA final code `ed1ab823...` : PENDING à la rédaction.** La présente note ajoute un commit documentaire et impose de vérifier les jobs `quality.yml` sur son HEAD exact avant qualification. Tests locaux hors CI : **NOT_TESTED**. Aucun PASS n'est attribué à une exécution en attente.

## Limitations et release gate
- **NOT_TESTED** : véritable serveur Temporal et workflow exécuté, HITL authentifié, tenant A/B, provenance signée Policy→Run→Evidence, impact SAN→Payments observé, E2E métier, rollback, Debian `applied.sha` et smoke-tests. Le `GET /api/runs/{id}` Core utilisé pour la cohérence d'identité n'est pas une preuve de RBAC tenant. Le `/health` Worker n'atteste pas Temporal.
- Le déployeur stable existant ne transporte pas automatiquement Worker/Policy/Core/Twin/Copilot/Evidence. Le poller stable ne valide aucun E2E ; l'assemblage multi-services est à qualifier sur un SHA unique par [Recette 5/5 #156](https://github.com/alimtalbi-ata/aiops/pull/156).
- **READY_FOR_STABLE=BLOCKED ; NO-GO E2E.** Aucun merge, push stable, accès Debian, effet LIVE, nouveau workflow CI ou résultat terrain inventé.
- Prochain lot Policy/HITL : exécution Temporal sandbox réellement éphémère avec commandes exclusivement DEMO, lien authentifié Policy→Run→Evidence et contrôle RBAC tenant ; remettre le SHA et les checks finaux à Recette 5/5, sans promotion autonome.
