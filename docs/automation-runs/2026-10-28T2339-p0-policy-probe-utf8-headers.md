# 2026-10-28 23:39 Europe/Paris — P0 sonde Core/Policy : JSON UTF-8 et en-têtes HTTP stricts

## État Git et coordination

- HEAD `main` revérifié avant modification : `13c455256f34e5e0f0ac55146326888b0fb84c42` ; base du présent lot inchangée depuis #160.
- HEAD de départ PR draft [#163](https://github.com/alimtalbi-ata/aiops/pull/163) : `03ee4aa4afae79904793a745f1cf552176d8d892`, branche `fix/p0-policy-probe-strict-json-20261028-2233` vers `main` ; revérifié avant les écritures. Aucun merge massif.
- `deploy/aiops2-stable` observé : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3` ; **non modifiée**. Aucun accès Debian.
- PR ouvertes et travaux concurrents vérifiés : #137 (Story), #140/#143/#145/#150/#152/#158/#166 (Studio), #142/#148/#157/#159/#165 (Twin), #149/#154/#161/#162/#167 (Ledger), #153/#156 (Recette), #163 (Policy). #144/#147/#155 sont fermées après portage ciblé via #160 ; #141 fusionnée. Les checks des SHA des PR #140–#146 ont été interrogés : #140 et #145 comportent des échecs parmi plusieurs runs, #142/#143 ont des runs verts sur leurs branches, #146 est conflictuelle et sa CI push ne vaut pas validation d'assemblage ; aucune promotion inférée.
- Continuité `docs/PROJECT-CONTINUITY.md`, journal `2026-10-28T2211-p0-core-policy-stack-convergence.md`, contrat `docs/demo/ACME-CORE-POLICY-OBSERVATION-V1.md` et workflow existant `.github/workflows/quality.yml` relus.

## Micro-livraison, commits, contrats

- `scripts/probe_demo_policy_readonly.py` : lecture de réponse Core en JSON **UTF-8 strict sans BOM**, au lieu de `json.loads(bytes)` qui accepte aussi UTF-16/UTF-32 ; refus des en-têtes `Cache-Control` et `Content-Type` dupliqués, `Content-Encoding` autre qu'identity, charset non UTF-8, cache sans no-store ou type non JSON. Aucun POST, aucune redirection/proxy, aucun accès distant ni LIVE.
- `tests/test_core_demo_policy_real_integration.py` : nouveau test positif avec **Core HTTP et PostgreSQL 16 réels éphémères CI** ; 5 cas négatifs d'encodage et 6 cas négatifs d'en-têtes, explicitement **tests de parseur/fixtures d'en-têtes** et non intégration simulée.
- `docs/demo/ACME-CORE-POLICY-OBSERVATION-V1.md` : transmission du contrat renforcé aux lots Story/Recette. API `aiops.core-demo-policy-observation.v1` et sortie CLI `aiops.demo-policy-readonly-probe.v1` inchangées ; entrées HTTP plus strictes. Les sorties `BLOCKED/MISSING`, `RESOLVED/PASS/SIMULATE` et `RUNNING` ne deviennent jamais preuve HITL/Temporal/LIVE.
- Commit code/tests/contrat `09073a6aa1bebc5ebe12805ab9d8386bc7b124a1` ; correctif des **littéraux de tests** BOM/octet invalide `dc857bae12181a37461821a8dbd6463fedfabb89`. Présent journal : commit supplémentaire. Aucun commit vide.
- `quality.yml` réutilisé **sans nouveau workflow** ni déclenchement manuel ; push et pull_request automatiques sur la branche `fix/**`.

## Tests et preuves disponibles au moment du journal

- Dernier SHA code/tests `dc857bae12181a37461821a8dbd6463fedfabb89` : [CI pull_request #40781807761](https://github.com/alimtalbi-ata/aiops/actions/runs/40781807761) et [CI push #40781800842](https://github.com/alimtalbi-ata/aiops/actions/runs/40781800842), **IN_PROGRESS lors de la rédaction**, aucun PASS revendiqué à ce stade.
- SHA intermédiaire `09073a6a` : [CI PR #40781781966](https://github.com/alimtalbi-ata/aiops/actions/runs/40781781966) et [CI push #40781773647](https://github.com/alimtalbi-ata/aiops/actions/runs/40781773647), en cours lors du contrôle. Le second commit corrige les fixtures d'octets ; la qualification doit porter sur le dernier HEAD.
- Vérification locale limitée : un extrait Python autonome des règles d'en-têtes a rejeté six variantes ; un extrait autonome de décodage UTF-8 a rejeté BOM/UTF-16/octets invalides. **Ce ne sont pas des tests du module du dépôt**. Suite intégrée locale : **NOT_TESTED**.
- **NOT_TESTED** : Policy HTTP réel, HITL authentifié, Temporal sandbox, postchecks, rollback, Evidence/AI Ledger, isolation tenant runtime, Twin SAN→Payments, Debian, `applied.sha`, les sept Runs rapportés (5 BLOCKED, 1 RESOLVED, 1 RUNNING ancien).

## Décision, risques et prochaine action

- **NO-GO E2E ; READY_FOR_STABLE = BLOCKED**. Les sept Runs proviennent du constat utilisateur, non revérifiés. `PASS/SIMULATE` est une gate persistée, pas une remédiation ; `BLOCKED/MISSING` n'en révèle pas la cause ; `RUNNING` n'atteste aucune terminaison.
- Risques : changement strict du transport (un consommateur UTF-16/compressé non conforme sera refusé) ; aucune attestation terrain ; branche stable divergente et déployeur Studio limité à `demo_v2.py`, `test_demo_v2.py`, injection `main.py` ; il ne transporte pas Core ni cette sonde.
- Prochain micro-lot : vérifier les trois jobs GitHub Actions sur **SHA final**, signaler les résultats et l'URL à Recette 5/5 [#156](https://github.com/alimtalbi-ata/aiops/pull/156), puis qualifier l'assemblage Core/Twin/Copilot/Studio/Evidence avec une recette authentifiée read-only. **Seul le lot 5/5** peut décider une promotion stable après couverture, rollback et preuves Debian authentiques.
