# 2026-10-29 02:24 CET — NOC/Copilot P0 — Policy DEMO ne doit pas afficher ALLOW LIVE

## État vérifié avant intervention
- HEAD `main` : `27deb9b1a66faf27df8d69b137a63451f7649d80` (#174, Policy/Core comparateur sans liaison Run attestée).
- Candidate NOC existante : PR #171, branche `release/p0-noc-ledger-converged-20261029-0004`, HEAD de départ `eb22e022c61e7b3c1d2dd5eb4b85758b5ac89e2e`. Pas de nouvelle pile de PR.
- PR ouvertes consultées : #169 UI, #170 Twin (SHA `37d4a210f970a8785ae26b2dbedcf378cf368407`, quality #40797616879 SUCCESS déclaré dans sa PR), #156 Recette 5/5, #153 déployeur, #175 garde applied.sha, #171 NOC et anciennes #145/#149/#154/#161/#162/#167. #141 et #144 fermées ; #140/#142/#143/#146 historiques toujours distinctes. Aucun état de ces PR n'est assimilé à un GO stable.
- Journaux NOC 01:27, Recette 23:50 et contenu de la PR Twin 02:00 consultés. Code `app/policy/main.py` sur main : `ALLOW` est émis seulement dans la branche LIVE ; en DEMO/REPLAY/STORY avec Evidence, la décision attendue est `SIMULATE`.

## UNE micro-livraison verticale
- `app/portal/demo_ledger_read.py` : garde stricte de disposition Policy sur un Run synthétique, décisions acceptées `SIMULATE/HUMAN_APPROVAL/ESCALATE/BLOCK/OBSERVE`, états `PASS/BLOCKED/UNKNOWN`. `ALLOW`, commandes d'effet LIVE et valeurs inconnues deviennent HTTP 503 `UNKNOWN`, sans détails privés, et `no-store`.
- `tests/test_demo_ledger_read.py` : mutations négatives ALLOW, EXECUTE, REMEDIATE, décision inconnue et état APPLIED ; test positif multi-Analysis/Policy existant conservé.
- `tests/test_demo_ledger_real_http.py` : nouveau cas de PostgreSQL 16 éphémère avec une ligne Policy `ALLOW/PASS` réellement persistée sur Run DEMO ; Core doit exposer la valeur brute à son client interne, mais Portal doit la refuser. Le test ne modifie aucun serveur réel.
- `docs/demo/ACME-PORTAL-LEDGER-EVIDENCE-REFS-V1.md` : contrat resserré, schéma JSON et routes inchangés. Contrat `aiops.demo-ledger-read.v1` : refus fail-closed additif ; aucun contrat Twin/Grafana/Policy Core modifié.
- Commits successifs : `60fa58a883e7da70237a2700cd9bea003da104d8` (code), `32307ccac41da15e9d7a844ea9f6a91d83710a08` (unit), `d11e3a1be17965dc8072e72df3e7869769b0cdc4` (HTTP réel), `ba853b3e50c79b1fb4155b3aa436c0b8c8ab5b82` (contrat). Le SHA de ce journal est à lire dans GitHub ; ne pas supposer que les anciens checks qualifient ce HEAD.

## Vérification, risques et release
- Tests locaux et PostgreSQL local : **NOT_TESTED** (checkout et services non disponibles dans ce créneau).
- `.github/workflows/quality.yml` existant : **PENDING / NOT_YET_VERIFIED** sur le SHA final du journal. Ne pas réutiliser la CI verte du SHA `eb22e022` pour qualifier les nouveaux commits. Aucun workflow créé.
- Risque de compatibilité : des décisions historiques inconnues deviennent `UNKNOWN` au lieu d'être présentées ; à qualifier par Recette. Le refus n'atteste ni exécution réelle Policy SIMULATE ni absence d'une action LIVE hors de cette projection.
- **READY_FOR_STABLE=BLOCKED / overall=NO_GO**. Il manque une candidate intégrée sur un SHA unique avec #169/#170, couverture du déployeur Core/Portal/Twin/Policy, ACL tenant A/B authentifiée, preuves métriques SAN/Payments, E2E Core→IA→Policy→Evidence→Studio, rollback et smoke-tests Debian avec `applied.sha` attesté.
- Aucune fusion, aucun push `deploy/aiops2-stable`, aucun accès Debian/NGX, aucune remédiation LIVE. La Recette 5/5 (#156) reste seule décisionnaire de promotion.

## Handoff / prochain lot
- Après contrôle de la CI sur le SHA final, transmettre à #156 : SHA #171, contrats resserrés, résultats des tests, statut BLOCKED et risque de compatibilité Policy.
- Prochain lot : recette intégrée et couverture de déploiement, pas une nouvelle PR NOC empilée.
