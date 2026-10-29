# 2026-10-29 09:02 Europe/Paris — ACME Twin P0 : refus des faux accusés synthétiques

## Source et coordination
- HEAD main lu : `27deb9b1a66faf27df8d69b137a63451f7649d80`; stable : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`.
- PR ouvertes, branches et journaux consultés : candidate ACME unique #170, fondée sur main ; #142 (direction inverse) et #148 (arêtes E08/E06/E04/E02/E01) déjà portées sans fusion historique. #156 est seul responsable de la recette et de la promotion. #176 Policy, #171 NOC et #177 UI ne constituent pas un E2E intégré.
- Dernière CI vérifiée **avant ce commit** : [quality.yml #40832515328](https://github.com/alimtalbi-ata/aiops/actions/runs/40832515328), completed/success, 3/3 jobs, sur `3f14fe28970de39c8f320d123e6121a2459fccd8`. Elle ne qualifie PAS le nouveau code.

## UNE correction P0 : accusé Twin `PASS` véridique
- Constat sur `app/twin/main.py` : `POST /api/twin/synthetic-event` renvoyait `status=PASS` pour une action inconnue, un `target_node_id` absent, ou un nœud inconnu, même si aucune opération n'avait eu lieu (ou si la base rejetait l'insertion).
- Le handler administrateur refuse maintenant les actions autres que `SET_STATE` et `OBSERVE` (422), l'absence de cible (422) et une cible non présente dans `aiops.twin_nodes` (404), **avant toute écriture**. Les deux actions reconnues, le contrat de succès, les routes GET, les migrations et la direction des arêtes sont inchangés. Aucune remédiation LIVE.
- Test ajouté au job Twin HTTP réel/PostgreSQL 16 de `quality.yml` existant : cinq refus avec credential administrateur éphémère, absence de `PASS`, et état SAN + compteurs de faits/observations inchangés. Aucun nouveau workflow.

## Qualification et limites
- Tests ciblés locaux : **NOT_TESTED** (pas de clone ni Docker local qualifié). CI sur le nouveau SHA : **PENDING / NOT_VERIFIED au moment du commit** ; ne pas reprendre les checks du parent comme validation.
- `SIMULATED / TOPOLOGY_ONLY` : SAN-A → stockage → VM → OraclePay → service → Payments par les arêtes SQL `ACME-E08/E06/E04/E02/E01`. Aucun SAN→hôte ni impact Payments runtime attesté. Le modèle Portal reste disjoint ; tenant ACL `false`.
- `NOT_TESTED` : worker Temporal complet, vrai appel positif de mutation synthétique en E2E, auth tenant A/B, provenance Core→IA→Policy→Evidence→Studio, transport multi-services, rollback, scrape Debian, `applied.sha` et smoke-tests sur SRV-DEB-05.

## Handoff
**READY_FOR_STABLE=BLOCKED / GO=NO-GO.** Ne pas promouvoir #170 sans CI finale verte sur SHA exact et sans assemblage par Recette 5/5, transport compatible, rollback et preuves Debian. Le déployeur #153 reste limité au portail ; le poller ne prouve pas E2E. Aucune fusion, aucun push stable, aucun accès Debian, aucun secret, aucune action LIVE.

Prochain lot : qualification intégrée du déployeur et des contrats Worker/Twin par #156 ; obtenir des preuves terrain horodatées et `applied.sha` observé avant GO.

## Qualification GitHub Actions observée après le commit de code
- PR candidate : [#170](https://github.com/alimtalbi-ata/aiops/pull/170), **SHA code+tests+journal** `ea553bad474adcdcbc7c46f3d50153e50f1568a6`.
- [quality.yml #40839566226](https://github.com/alimtalbi-ata/aiops/actions/runs/40839566226) : **3/3 jobs completed/success** sur ce SHA. Logs du job Core/PostgreSQL lus : **15/15 Twin HTTP réel + PostgreSQL 16**, dont `test_admin_synthetic_event_refuses_noop_receipts_without_mutation ... ok`; **2/2 Prometheus réel**, **14/14 Core/Policy**, **8/8 Policy HTTP**, **5/5 NOC**. Jobs Grafana et statique également SUCCESS.
- Le présent addendum crée un **nouveau SHA documentaire** : la CI ci-dessus qualifie le SHA code, pas automatiquement le HEAD documentaire. Vérifier la CI du nouveau HEAD avant tout handoff ; aucune preuve de recette terrain.
