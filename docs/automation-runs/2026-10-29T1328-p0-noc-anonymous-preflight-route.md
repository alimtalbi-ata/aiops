# 2026-10-29 13:28 CET — NOC 3/5, correctif P0 préflight anonyme sur candidate #185

**READY_FOR_STABLE=BLOCKED / NO-GO.** Correctif ciblé dans la PR d'intégration existante [#185](https://github.com/alimtalbi-ata/aiops/pull/185), sans nouvelle PR ni route ni workflow CI. Base de travail `2c8571af026401e87ffe2ce0ab1c540167a7fb82`; le SHA de ce journal sera le SHA du commit résultant (à vérifier après écriture). Aucun push stable, accès Debian ou action LIVE.

## Diagnostic vérifié

- Le script `scripts/check_demo_field_readonly.py` appelait `GET /api/noc/runs/SMOKE-UNAUTH` et exigeait HTTP 401, mais **cette route n'existe pas**. Elle retourne 404 ; ce refus ne prouve pas l'auth.
- `app/core/demo_evidence_read.py` enregistre `GET /api/noc/runs/{rid}/evidence-refs` via `register_demo_evidence_routes` ; son handler appelle `auth(bearer(authorization))` **avant tout accès DB**. Le Core enregistre aussi `GET /api/runs/{rid}/ai-ledger`.
- Dans [les observations opérateur de #185](https://github.com/alimtalbi-ata/aiops/pull/185#issuecomment-6496619221), la route réelle `/api/noc/runs/SMOKE-UNAUTH/evidence-refs` a renvoyé **HTTP 401 sans jeton** depuis le conteneur Core Debian sur l'image **e94fe784**, et l'ancienne cible 404. Observation opérateur, pas validation indépendante du HEAD GitHub actuel.

## Contrat et livraison minimale

- Remplacer uniquement l'URL du test négatif dans `scripts/check_demo_field_readonly.py` par la route canonique `/api/noc/runs/SMOKE-UNAUTH/evidence-refs`, **sans modifier l'exigence HTTP 401**. 403/404/200/503 restent BLOCKED ; aucune requête authentifiée ni jeton, aucun POST, aucune redirection ni mutation.
- Aligner le serveur HTTP fixture `tests/test_demo_field_readonly.py` sur la route existante, et ajouter le test explicite **404 ⇒ BLOCKED**.
- Ajouter cette suite ciblée dans **l'étape existante** de `.github/workflows/quality.yml`, sans workflow supplémentaire. L'ensemble reste un préflight read-only `overall=NO_GO`, pas une preuve E2E ni une qualification RBAC tenant.

## Qualité et limites

- Avant correctif, [quality.yml #40868269128](https://github.com/alimtalbi-ata/aiops/actions/runs/40868269128) sur `2c8571af026401e87ffe2ce0ab1c540167a7fb82` : **completed/success, 6/6 jobs** ; V2.8 #40868269156, Offline #40868269090, Historical #40868269144 : SUCCESS.
- Après correctif : **CI du SHA final à vérifier** ; aucun résultat anticipé. Tests locaux : **NOT_TESTED** ; tests Debian du SHA corrigé : **NOT_TESTED**. La réponse 401 observée sur e94fe784 n'atteste pas l'image future.
- Contrats JSON et API Core/Portal/Twin/Policy **inchangés**. Seuls le chemin du préflight et sa couverture fixture/CI changent.
- Risques P0 non résolus : UI run/tenant fail-closed, `/metrics` Twin, Worker redondance, absence d'un run ACME SAN→Payments→Analysis→Critique→Policy SIMULATE→Evidence→Studio attesté, déployeur/poller portal-only, rollback et `applied.sha` non qualifiés pour le SHA intégré.

**Handoff 5/5 :** vérifier le nouveau HEAD #185 et ses checks, faire rejouer le préflight depuis un checkout exact sur environnement autorisé avec reçus horodatés, conserver `NO_GO` tant que les autres gates et le rollback ne sont pas prouvés. Ne pas promouvoir `deploy/aiops2-stable`.
