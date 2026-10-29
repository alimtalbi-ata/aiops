# 2026-10-29 01:27 CET — P0 NOC/Copilot — Policy↔Analysis/Critique referential fence

## Baseline et coordination
- `main` lu avant modification : `64b9f9aa7abae4b35bda2bf881defbe062268bce`.
- Candidate unique NOC #171 : branche `release/p0-noc-ledger-converged-20261029-0004`, SHA de départ `c7b143c64eb5127d9ae690fbf35799ee1ffb0ef6`, vérifié juste avant écriture.
- PR ouvertes consultées : #171 (NOC), #169 (UI), #170 (Twin), #156 (Recette 5/5), #153 (déploiement) ; historiques #145/#149/#154/#161/#162/#167 conservés comme sources, sans nouvelle pile.
- Journaux NOC 00:04 et 00:21, documentation Core/Portal et migrations 009 consultés. La table `aiops.policy_decisions` possède des FK Analysis/Critique **sans contrainte de même Run** ; la projection Portal ignorait ces deux liens.

## Micro-livraison
- Fichiers : `app/portal/demo_ledger_read.py`, `tests/test_demo_ledger_read.py`, `tests/test_demo_ledger_real_http.py`, `docs/demo/ACME-PORTAL-LEDGER-EVIDENCE-REFS-V1.md`, présent journal.
- Refus de Policy décisions sans lien, avec identifiants dupliqués, avec Analysis/Critique d'un autre Run ou avec Critique rattachée à une autre Analysis. Test positif multi-Analysis et liens partiels valides.
- Test HTTP réel éphémère : insertions SQL synthétiques isolées, Policy SIMULATE/PASS **enregistrée** sur Run valide puis seconde décision citant Analysis/Critique d'un autre Run ; réponse Portal attendue 503 `UNKNOWN`, sans fuite.
- Contrat : `aiops.demo-ledger-read.v1` schéma inchangé, fail-closed renforcé ; Core `aiops.core-demo-evidence-refs.v1` inchangé. Aucun contrat de tenant ACL ajouté. Aucune attestation d'exécution Policy ou de métriques observées.

## Tests / CI
- Tests locaux : NOT_TESTED (pas de checkout de dépôt ni PostgreSQL local qualifié).
- GitHub Actions `quality.yml` existant : PENDING sur le SHA du présent commit ; ne pas déclarer PASS avant résultat GitHub authentique.
- Aucun nouveau workflow ni secrets de production.

## Risques / blocages / release
- **READY_FOR_STABLE=BLOCKED / NO-GO**. La CI verte historique de #171 ne se transfère pas au nouveau SHA.
- Déployeur actuel ne transporte pas Core/Portal complet ; impact Twin Payments, métriques SAN observées, tenant A/B authentifié, E2E Policy SIMULATE, Ollama, rollback et `applied.sha` Debian : NOT_TESTED.
- Aucun push sur `deploy/aiops2-stable`, aucun merge, accès Debian, commande LIVE ou NGX.
- Prochain micro-lot : requalifier `quality.yml` sur SHA final, remettre SHA et résultats à #156 ; Recette 5/5 seule habilitée à assembler et promouvoir après couverture de déploiement, rollback et smoke-test terrain.
