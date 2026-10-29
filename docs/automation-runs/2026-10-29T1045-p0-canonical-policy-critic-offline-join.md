# 2026-10-29 10:45 CET — Recette 5/5 : Policy→Critique→Analysis canonique, offline

## État de release et inventaire consulté
**READY_FOR_STABLE=BLOCKED / NO-GO**. HEAD main `27deb9b1a66faf27df8d69b137a63451f7649d80` ; stable `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`. Git stable→main : **diverged (ahead 43 / behind 633)** ; stable→#153 : **ahead 39 / behind 0**, mais diff incompatible avec le poller. Aucun merge main/stable.

PR ouvertes et branches de livraison vérifiées : #153 déployeur `e5c6b030c374e47f64678f425df78cd147335eec` (quality [40819754378](https://github.com/alimtalbi-ata/aiops/actions/runs/40819754378) SUCCESS) ; #156 Recette base `6cc6679d26b23021bd5f2d8b2bf9d0f361fd7c04` (quality [40845132420](https://github.com/alimtalbi-ata/aiops/actions/runs/40845132420) SUCCESS) ; #170 Twin `bec96d26b288394a8c4d878417090e09c8c52a25` (quality [40847018907](https://github.com/alimtalbi-ata/aiops/actions/runs/40847018907) SUCCESS) ; #171 NOC/Evidence `a46b5d0972a10b78ac1a490257bf543592ba3c2b` (quality [40849991573](https://github.com/alimtalbi-ata/aiops/actions/runs/40849991573) SUCCESS) ; #176 Policy/Worker `b56488d9ff80c8166c9dd9cf64f24d0b7e3d48c8` (quality [40850869523](https://github.com/alimtalbi-ata/aiops/actions/runs/40850869523) SUCCESS) ; #177 UI `a539b293d5bc01d6cd71ff6dc5b53b382baa793c` (quality [40847845287](https://github.com/alimtalbi-ata/aiops/actions/runs/40847845287) FAILURE). Ces succès sont **isolés**, jamais une CI d'assemblage.

Anciennes #140–#146 revues sur HEAD exact : #140 FAILURE, #141 fusionnée/SUCCESS, #142 SUCCESS, #143 SUCCESS, #144 fermée non fusionnée/SUCCESS, #145 FAILURE, #146 sans quality run trouvé. Ne pas dupliquer les correctifs Twin/UI historiques. Journal précédent lu : `2026-10-29T0944-p0-release-receipt-aggregate.md`.

## Livraison verticale, branche dédiée
Branche `fix/p0-receipt-policy-critic-canonical-20261029-1045` issue de #156 `6cc6679`, PR candidate vers la branche de développement #156 **uniquement**. Code `c763911cc17eab0cd1bcdbb5fc26d5e4dedede55`, tests `288e4237f48034298c193a8b11a18934fa9d448d`.

- **P0 découvert :** `scripts/check_demo_evidence_receipts.py` exigeait l'ancien schéma Policy à 3 clés et rejetait les exports canoniques #171 (`analysis_id`, `critique_id`). Pire : un `SIMULATE/PASS` pouvait être accepté si **une autre** Critique du Run était validée, sans lien Policy→Critique spécifique.
- Contrat renforcé `aiops.demo-evidence-offline-receipt.v1` (version inchangée, sémantique stricte) : cinq clés exactes pour chaque décision ; identifiants canoniques reliés à la même Analysis et au même Run, refus des clés manquantes/étrangères, liens croisés, doublons et dispositions LIVE ; `SIMULATE/PASS` exige **sa propre** Critique `validated=true` et son Analysis `status=VALID`. Les décisions historiques `BLOCK/BLOCKED` restent lisibles, liens nullables uniquement si le lien restant est valide.
- Tests de fixtures ajoutés : liens absents, étrangers, cross-analysis, Critique non validée malgré autre Critique valide, Analysis `INVALID/UNAVAILABLE/SUPERSEDED/COMPLETE`, cas historique BLOCK, absence de fuite. Les tests agrégateur existants réutilisent la fixture canonique.
- `checks.recorded_policy_critic_join=PASS_UNATTESTED` indique **uniquement la cohérence des JSON opérateur**. `policy_critic_linkage_origin=NOT_TESTED`, `overall=NO_GO`, `ready_for_stable=BLOCKED` via agrégateur inchangés. Les reçus Evidence sont des références, pas une validation indépendante.
- Pas de nouveau workflow ; `.github/workflows/quality.yml` existant exécute `tests/test_demo_evidence_receipts.py`.

## Matrice modules modifiés → transport / rebuild / restart / tests / rollback
| Domaine | Copie / rebuild / restart | Tests | Rollback | Verdict |
| --- | --- | --- | --- | --- |
| `scripts/check_demo_evidence_receipts.py`, `tests/test_demo_evidence_receipts.py` | Outils de recette hors ligne, **non transportés par le déployeur #153** | quality.yml sur branche candidate, résultat à confirmer | Sans mutation runtime ; retour au SHA précédent | REVIEWABLE pour revue seulement |
| Portal Demo Studio `demo_v2.py` | Copie/rebuild/restart ciblés par #153 | CI isolée ; terrain NOT_TESTED | Docker/source NOT_TESTED | BLOCKED |
| Core / Twin / Copilot / Policy / Worker / Evidence | **Aucune copie/rebuild/restart qualifiée** par #153 | CI séparées, pas d'assemblage | **Non couvert** | BLOCKED |
| `deploy/*`, `.github/*`, `app/policy/main.py` dans stable→#153 | Poller actuel bloque ces chemins | Requalification du déployeur et CI nécessaires | Non qualifié | BLOCKED |

## Qualification GO/NO-GO et recette
- Tests locaux : **NOT_TESTED** (pas de runtime source complet local). CI candidate `quality.yml` : **PENDING** à la rédaction ; relever les jobs exacts après le dernier SHA, ne pas extrapoler la CI de #156.
- Recette opérateur **read-only** : récupérer sous autorisation Core `/api/runs/{rid}/evidence-refs` et Portal `/api/demo-studio/runs/{rid}/ai-ledger` sur loopback, conserver JSON séparés, exécuter `python scripts/check_demo_evidence_receipts.py --run-id RUN-DEMO --ledger-file /abs/ledger.json --refs-file /abs/refs.json`, puis l'agrégateur `check_demo_release_receipts.py` avec couverture Git, smoke et SHA. Aucun token dans les journaux. Même un PASS offline = **NO_GO**.
- **NOT_TESTED** : vrai `incident_id` et Run/Evidence terrain, Temporal exécuté, Analyst/Critic/Policy originaux, isolation RBAC tenant A/B, impact SAN→Payments, authentification et attestation indépendante des reçus, rollback Docker, cron Debian `applied.sha` et smoke SRV-DEB-05. Ne pas confondre `runtime-e2e` CI avec parcours ACME.
- **Blocage unique promotion :** aucun candidat multi-services assemblé avec transport, restart, tests et rollback qualifiés ; UI #177 rouge. Prochain acte : figer les SHAs par domaine, résoudre UI, construire déployeur couvrant réellement tous les modules, CI intégrée rapide+complète, recette terrain en lecture seule et preuve Debian indépendante. Si impossible, garder une PR de revue et NO-GO.

Aucune promotion stable, aucun accès Debian, aucune mutation LIVE, aucun secret.
