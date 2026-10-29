# P0 NOC/ITSM — alignement Evidence vide avec le Ledger Portal (29/10/2026 ~19:24 CET)

**Code/tests commit :** `0dc30d181c9b9bd437101bdc032771ae15ac73ed` sur `prep/acme-demo-offline-20261029` (parent `0ca854fe8a0d657312175fb55ee5aa22def981cd`). **READY_FOR_STABLE=BLOCKED ; DEMO_READY Debian=NOT_READY.** Issue de référence #186 ; candidate unique release #185, pas de nouvelle PR. Aucun changement `app/portal/main.py`, Docker, stable, DB ou LIVE.

## Blocage de contrat démontré et correctif minimal

Sur la candidate #185, `app/portal/demo_ledger_read.py:_evidence_ids` autorise `[]` sur une Analysis ou une Critique historique ; la qualification Core impose néanmoins un ensemble Run-wide de références Evidence non vide. Le raccord `app/shared/acme_itsm_evidence_link.py:_ids` rejetait toute liste vide, masquant comme `UNKNOWN` un Run pourtant projetable par le Ledger Portal. Ce défaut a été reproduit avec deux tests rouges avant correction.

**Correction :** autoriser une liste vide **uniquement au niveau de chaque Analysis/Critique** ; conserver la condition `1 <= len(evidence_refs) <= 80`, la correspondance exacte des ensembles d'Evidence Run-wide, l'identité Run/incident, les liens Analysis→Critique→Policy et le rejet de références étrangères. Pas d'élargissement de privilèges. Une Critique sans citation ne prétend pas soutenir un diagnostic.

**Fichiers :** `app/shared/acme_itsm_evidence_link.py` (Git blob `19c4e82affd5757f0e6edd11bc933db57f6518eb`) ; `tests/test_acme_itsm_evidence_link.py` (Git blob `e6b86713b96d6668bb97599b5f534d67db50e6c8`). Blobs testés localement puis identifiés à l'identique lors de la publication GitHub.

## Résultats réellement exécutés

- Avant correction : `python3 -m unittest discover -s tests -p test_acme_itsm_evidence_link.py -q` → 16 tests, **2 FAIL** (analyses/critiques historiques sans citation).
- Après correction : `python3 -m unittest discover -s tests -p test_acme_itsm_evidence_link.py -v` → **16/16 PASS** ; `python3 -m py_compile app/shared/acme_itsm_evidence_link.py tests/test_acme_itsm_evidence_link.py` → **PASS**. Tests exécutés dans un checkout local isolé contenant les deux blobs Git exacts, sans dépendance externe.
- Négatifs : toutes les références absentes ou étrangères restent `UNKNOWN` ; faux HMAC, mismatch de Run, LIVE, tenant non qualifié et données manquantes sont refusés par les tests existants.
- CI `quality.yml` du commit prep : **NOT_RUN**. La CI verte de #185 sur `e18347e17a44ab56e3437bda94557d841d0908b8` ne couvre PAS ce correctif.
- HTTP Core/GLPI, RBAC tenant A/B, serveur Debian, rollback, `applied.sha`, E2E SAN→Payments : **NOT_TESTED**.

## Contrat et handoff 2/5 / 5/5

`project_itsm_evidence(core_detail, ledger, signed_noc=None)` reste une fonction pure sans I/O ni autorisation : les snapshots doivent venir des lecteurs serveur Core/Portal existants, après viewer auth et fail-closed tenant. Sortie `aiops.acme-itsm-evidence-link.v1`, `CORRELATED_UNATTESTED` ou `UNKNOWN`, `SYNTHETIC_ONLY`, `ticket_id=null`, `tenant_acl_qualified=false`, `runtime_attested=false`. Une revendication NOC HMAC est seulement `glpi_ticket_claim`, jamais un ticket GLPI lu dans son API. Pas de preuve Payments ou d'effet LIVE.

**Écran cible :** `/demo-studio/run/{rid}` puis `/evidence` dans le portail existant, uniquement si 2/5/5/5 choisissent de monter ce raccord et de qualifier son lecteur autorisé. La candidate #185 possède déjà `/demo-studio` et `/demo-studio/business-story` ; **ce module n'est pas monté** et ne doit pas être présenté comme visible/déployé. Le poller Debian portal-only ne transporte pas automatiquement `app/shared/`.

**Action unique pour 5/5 :** reprendre les deux fichiers seulement si le chemin visible les consomme, exécuter `python3 -m unittest discover -s tests -p test_acme_itsm_evidence_link.py -v` puis `quality.yml` sur le SHA intégré ; vérifier packaging, rollback et smoke read-only opérateur avant toute promotion. Sinon laisser ITSM/GLPI `UNKNOWN` et ne pas retarder la démo existante.
