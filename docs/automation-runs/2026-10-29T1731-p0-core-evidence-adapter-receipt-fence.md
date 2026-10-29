# 2026-10-29 — Policy/HITL 4/5 : refus de reçus falsifiés dans l'adaptateur Core Evidence

**READY_FOR_STABLE=BLOCKED / E2E NO-GO.** Branche partagée de préparation `prep/acme-demo-offline-20261029` ; pas de nouvelle PR, aucun push stable, aucun déploiement Debian/Docker, aucun LIVE. Directive #186 relue ; `main=27deb9b1a66faf27df8d69b137a63451f7649d80`, `deploy/aiops2-stable=e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`. Candidate d'intégration #185 HEAD au moment de la lecture : `ad05690003ccca919e4cf0cd4a33d495becfaab0`, draft, quality.yml 40905698722 SUCCESS (6/6 jobs), workflows historiques SUCCESS. La source Policy #176 reste `b56488d9ff80c8166c9dd9cf64f24d0b7e3d48c8`.

## Défectuosité P0 reproduite par lecture du code

Au commit précédent `f100945cfa772b67b0c99955167c07d41c6b8c3a`, `normalize_core_evidence_refs(receipt, response)` vérifiait le schéma et l'ensemble des IDs mais pas l'identité `run_id` du reçu, ni ses indicateurs d'effet/attestation. Un reçu avec `run_id=None` et une réponse assortie `run_id=None`, ou un reçu revendiquant `effect_applied=true`, pouvait retourner `CONSISTENT_UNATTESTED`. Cela n'aurait toujours pas attesté Core, mais aurait produit un signal de cohérence trompeur pour un reçu dangereux.

**Correction minimale, sans HTTP ni nouveaux composants :**
- `app/shared/acme_core_evidence_adapter.py` : `UNKNOWN/UNSAFE_RECEIPT_CLAIMS` pour classification autre que `SYNTHETIC_UNVERIFIED` ou claims `core_run_verified`, `evidence_verified`, `effect_applied`, `persisted` non strictement faux ; `UNKNOWN/RECEIPT_IDENTITY_UNQUALIFIED` pour `run_id` absent/malformé.
- `tests/test_acme_core_evidence_adapter.py` : 4 tests négatifs supplémentaires, total 16.
- Commits code `e7e2227f5dc88db602a3d56dc0e879251fef75f7`, tests `c9a85f830b418204e89b18747dc85b76af20c837`.

## Tests effectivement exécutés (environnement éphémère local, pas Debian)

`python3 -m unittest discover -s tests -p test_acme_core_evidence_adapter.py -v` : **16/16 PASS**, 0.001s, sur copies **byte-for-byte** des deux fichiers GitHub (SHA Git blob module `eca7067f6378224e42a2b367e61aa76f6745c784`, tests `3af982a6ae299f92e92533f2c8c15202bc05d81f`, vérifiés par `git hash-object`). **Limite explicite :** `app.shared.acme_demo_offline.demo_receipt` a été remplacé par un stand-in local minimal, de même forme pour les champs utilisés ; ce résultat valide le comportement de l'adaptateur et ses 16 assertions, **pas** l'exécution du dépôt complet ni les dépendances du vrai générateur de reçu.

La preuve Debian **44/44 PASS + 26/26 preflight statique** reste limitée au SHA `0d7f2ac`. Les 12 tests initiaux de l'adaptateur étaient NON exécutés sur Debian ; avec les 4 nouveaux tests, le total théorique des six suites est **60 tests**, **pas 60 PASS Debian**. `quality.yml` ne se déclenche pas sur les pushes `prep/**` et aucun nouveau workflow n'a été créé. La CI verte #185 ne teste pas ce nouveau commit.

## Contrats et limites

`normalize_core_evidence_refs` demeure une normalisation **présentation uniquement** : `SYNTHETIC_UNVERIFIED`, `core_run_verified=false`, `evidence_verified=false`, `tenant_acl_qualified=false`, `runtime_attested=false`, `effect_applied=false`. `CONSISTENT_UNATTESTED` signifie seulement concordance des références fournies par l'appelant. `GET /api/noc/runs/{rid}/evidence-refs` exige un Bearer et des liens Analysis/Critique/Events, mais renvoie expressément `tenant_acl_qualified=false` et `runtime_attested=false`; il n'autorise pas la qualification tenant. Ne pas fabriquer `source_qualified`, `synthetic` ou `run_id` dans les `items` pour appeler `qualify_receipt`.

**NOT_TESTED :** vrai `demo_receipt()` dans le dépôt cloné, CI sur la branche prep, PostgreSQL/HTTP Core, authentification/tenant A-B, run_id/evidence_ids Core réels, Temporal/HITL GLPI, E2E SAN→Payments, `applied.sha`, rollback et Debian au nouveau SHA. Le `RUN-ACME-OFFLINE-001` et les `EVD-ACME-OFFLINE-*` restent des fixtures. Les 5 BLOCKED/1 RESOLVED/1 RUNNING historiques ne sont pas revérifiés ; `RESOLVED/PASS/SIMULATE` ne prouve pas de remédiation LIVE.

**Handoff exclusif à Recette 5/5 :** intégrer seulement après revue de cette modification sur prep, exécuter les 60 tests du dépôt dans un checkout isolé, qualifier `quality.yml` sur un SHA d'intégration, puis traiter la vraie lecture read-only authentifiée et tenant-scoped séparément. L'adaptateur n'est pas une attestation et ne doit pas être branché comme un succès dans Demo Studio. Le poller stable reste portal-only, et le transport multi-services/rollback est BLOCKED.
