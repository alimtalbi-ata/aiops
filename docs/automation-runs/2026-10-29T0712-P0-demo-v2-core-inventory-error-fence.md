# 2026-10-29 07:12 Europe/Paris — P0 UI : inventaire Core non vérifié interdit pour Demo Studio V2

## HEAD, PR et coordination
- HEAD `main` lu sur GitHub : `27deb9b1a66faf27df8d69b137a63451f7649d80`. Stable `deploy/aiops2-stable` : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`, **non modifiée**.
- Candidate existante [PR draft #177](https://github.com/alimtalbi-ata/aiops/pull/177), branche `ui/p0-demo-v2-core-detail-envelope-20261029-0307`, base #169, cumulant #140→#150→#152→#158→#166→#169. Pas de nouvelle PR ni de workflow.
- PR consultées : #141 fusionnée ; #144 fermée non fusionnée ; #140/#142/#143/#145/#146 et pile UI ouvertes ; #153 déployeur, #156 Recette 5/5, #170 Twin, #171 NOC, #176 Policy ouvertes draft. Branches récentes et journaux consultés : UI 06:10, Recette 06:49, Twin 06:55, poller 05:43. Aucun de ces résultats isolés n'atteste un assemblage E2E.
- Commits de ce lot : `7821cddee78ac6eefb6d4a3bb8a836358743defe` (code), `add7090a6b629b1856352fcbd50b7e5b496e6243` (tests). SHA de tête après ce journal à relever sur la PR.

## UNE livraison verticale mesurable : inventaire Core fail-closed
- Défaut identifié : `_runs()` acceptait `items` même dans une enveloppe Core `status=UNKNOWN/ERROR` ou `error_type=HTTPError`. Un inventaire d'erreur contenant un faux run DEMO pouvait autoriser `/demo-studio/run/{rid}` et `/api/demo-status/{rid}` à demander les détails et registres.
- `app/portal/main.py` : `_runs(strict=True)` refuse les enveloppes non `OK`, erreurs de transport, `items` absents/malformés ou entrées non dictionnaires. Le résultat `None` distingue une lecture **INCONNU** d'un inventaire vide authentiquement lu (`[]`). Les routes Demo Studio utilisent ce mode strict ; les autres pages conservent le contrat historique `_runs()`.
- Préflight `Scénarios DEMO/REPLAY/STORY visibles` affiche `INCONNU — inventaire Core indisponible` en cas de source non vérifiable, jamais `0` ni un run forgé. Détail/poll refusent l'accès avant toute lecture Core détail, AI Ledger ou Policy.
- `tests/test_v28_portal_ui.py` : 2 tests couvrant 6 enveloppes adversariales (dont HTTP 401 avec faux `items`), aucun lien/identifiant forgé, aucune lecture privilégiée et aucun POST ; positif inventaire vide lisible.
- Contrats Core/Twin/Copilot/Policy/Evidence/API inchangés. Contrat d'affichage Demo Studio resserré : `INCONNU` distinct de zéro, sans faux résultat LIVE, sans causalité Payments ni effet production.

## CI et NOT_TESTED
- Tests locaux : **NOT_TESTED** (pas de checkout exécutable local) ; aucun test ni accès Debian.
- CI existante [quality.yml #40827879861](https://github.com/alimtalbi-ata/aiops/actions/runs/40827879861) sur le SHA code+tests `add7090a6` : logs du job `quality-build-package` consultés : **5 tests source-auth + 16 tests Demo V2 + 41 tests portail = 62/62 PASS**, incluant les 2 nouveaux ; compilation Python PASS. Étape `Policy safety unit tests` **FAILURE : 11/15 échecs**, `AUTONOMY_STATE_UNAVAILABLE` et assertions historiques. Job `quality-build-package` FAILURE ; `runtime-e2e` et autres jobs étaient encore en cours au relevé.
- La CI du SHA documentaire final devra être vérifiée séparément. Aucune dérogation à `quality.yml` ni ajout de workflow.
- **NOT_TESTED** : navigateur authentifié, RBAC/tenant en runtime, liaison SAN→Payments, Core→Temporal→Analyst/Critic→Policy SIMULATE→Evidence→Portal, preuve synthetic/run_id/evidence authentifiée, transport de `main.py`, rollback et `applied.sha`/smoke-tests sur SRV-DEB-05.

## Transport et décision
- Le déployeur #153 injecte `app/portal/main.py` partiellement et ne transporte pas ce correctif arbitraire de `main.py` ; la matrice #156 exige couverture, rebuild/restart, rollback et preuves terrain avant promotion. Les changements Core/Twin/Copilot/Policy/Evidence ne sont pas automatiquement transportés.
- **BLOCKED / READY_FOR_STABLE=false / NO-GO**. Échéance 05h dépassée ; qualité Policy rouge, runtime E2E non qualifié, transport et rollback non validés. Aucune fusion, aucun push `deploy/aiops2-stable`, aucun accès Debian, aucune remédiation LIVE.
- Prochain lot : transmettre le SHA exact à Recette 5/5 #156 ; figer un SHA intégré avec transport complet, obtenir quality.yml intégrale verte et recette read-only, puis seulement faire attester `applied.sha` et les smoke-tests par l'opérateur Debian. Ne jamais déduire GO du seul poller.
