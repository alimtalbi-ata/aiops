# 2026-10-29 04:14 Europe/Paris — P0 UI : AI Ledger lié à l'identité Core

## État des sources et périmètre
- HEAD main lu : `27deb9b1a66faf27df8d69b137a63451f7649d80` ; stable `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3` inchangée.
- PR UI #177 (draft) https://github.com/alimtalbi-ata/aiops/pull/177, branche `ui/p0-demo-v2-core-detail-envelope-20261029-0307`, empilée sur #169, donc pile #140→#150→#152→#158→#166 incluse. Commit code+tests : `9c0410a662b6ca7d07c25d2d2468d1eda3aa5e20` (parent `a327c2258572330d3cb8604401411031322b8df3`). Le SHA de tête après ce journal doit être vérifié sur #177 ; pas de promotion isolée.
- PR examinées : #141 fusionnée, #142/#143/#145/#146 ouvertes, #144 fermée sans fusion ; #153 déployeur, #156 Recette, #170 Twin, #171 NOC, #176 Policy, #177 UI ouvertes. Journaux lus : UI `2026-10-29T0307-P0-demo-v2-core-detail-envelope.md`, Recette `2026-10-29T0048-p0-stable-transport-matrix.md`, Policy `2026-10-29T0144-p0-policy-core-unbound-crosscheck.md`.
 
## UNE micro-livraison mesurable
- `app/portal/main.py` : nouvelle projection `_verified_demo_ledger` sur les seuls parcours `/demo-studio/run/{rid}` et `/api/demo-status/{rid}`. Les claims explicites `run_id`/`tenant_id`/`tenant` du Ledger (enveloppe, items, sections analysis/critic dictionnaires) doivent correspondre au run Core déjà vérifié. Un conflit, une forme items invalide ou une enveloppe d'erreur renvoie `status=UNKNOWN`, sans contenu Analyst/Critic potentiellement étranger dans HTML brut, explication Critic ou polling JSON.
- 401/403 capturés restent distincts dans la projection sans recopier URL, corps ou secret. Une absence de claims n'est PAS une attestation d'identité : elle reste compatible avec le contrat Ledger actuel, qui peut omettre ces champs.
- `tests/test_v28_portal_ui.py` : deux tests nouveaux, cinq cas négatifs (autre run, autre tenant, item étranger, analyse imbriquée étrangère, erreur HTTP 401 avec contenu forgé) sur HTML + polling, et positif source concordante. Aucun appel d'écriture ni action LIVE.

## Contrat et compatibilité
- Endpoints publics inchangés. Le contrat d'affichage de Ledger est resserré : en cas d'identité ou de source non vérifiable, `ledger.status=UNKNOWN` ; si un HTTP 401/403 a été capturé, seul `error_type=HTTPError` et `http_status` minimal sont conservés. Les sources concordantes restent visibles, **non attestées indépendamment**.
- Ne pas modifier Core/Twin/Policy, ni la provenance ACME. Ce lot ne prouve pas le lien SAN→Payments, la causalité IA→Policy, ni une preuve Evidence authentifiée.
- Déployeur #153 : `main.py` n'est injecté que partiellement ; ce changement n'est pas automatiquement transporté. Recette #156 doit vérifier couverture, rollback, auth/RBAC, modules et SHA appliqué avant GO.

## Tests et décision
- Tests locaux : NOT_TESTED (pas de checkout exécutable ni de serveur Debian accessible depuis cette exécution).
- CI code+tests : https://github.com/alimtalbi-ata/aiops/actions/runs/40811196498 (`quality.yml`, QUEUED au relevé initial). Les résultats doivent être lus sur le SHA final après journal ; ne pas inférer de PASS.
- CI historique #177 : https://github.com/alimtalbi-ata/aiops/actions/runs/40804698348 **FAILURE** (11 assertions Policy rapportées, runtime E2E non qualifié). Les 54 tests UI ciblés PASS étaient ceux du SHA antérieur, pas du présent correctif.
- **BLOCKED / READY_FOR_STABLE=false / NO-GO** tant que quality.yml global, runtime E2E, déployeur et recette restent non qualifiés.
- **NOT_TESTED** : navigateur authentifié, isolation tenant runtime, contrat Ledger sur Core réel, SAN→Payments→IA→Policy SIMULATE→Evidence→Portal, rollback, applied.sha, smoke-tests Debian.
- Prochain lot : vérifier quality.yml du SHA final et transmettre à Recette 5/5 la candidate #177, sans pousser `deploy/aiops2-stable`. Seul Recette 5/5 décide de la promotion après preuves de bout en bout.
