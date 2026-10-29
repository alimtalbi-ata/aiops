# ACME — Audit d'architecture transversal et feuille de convergence, 2026-10-29

## Périmètre et méthode

Lecture effective de branches historiques par comparaison GitHub contre `prep/acme-demo-offline-20261029`, puis lecture de fichiers ciblés. Ce rapport distingue **fichier existant**, **contrat inspecté**, **test Debian réellement rapporté**, et **intégration E2E non prouvée**. Ne pas utiliser les nombres ahead/behind de GitHub comme une mesure de qualité : ces branches ont divergé et contiennent des composants qui peuvent être plus anciens.

## Résultats du code inspecté

| Fonction métier | Source historique vérifiée | Constat | Stratégie |
|---|---|---|---|
| Remédiation/HITL | `feat/p0-hitl-remediation-lab-simulator-20261027-2024:app/shared/remediation_lab.py` et catalogue | 8 recettes SIMULATOR_ONLY, approbation fixture, refus LIVE, secrets masqués | **Déjà porté** sur prep, 10 tests Debian PASS |
| Projection avant/après | `prep:app/shared/acme_remediation_projection.py` | Simulation pure, échec/rollback projetés ; nouvelle garde contre faux rétablissement par recettes read-only | Tester sur Debian après la dernière modification |
| Liaison run/preuves | `prep:app/shared/acme_remediation_receipt.py` | Identifiants/digest cohérents, mais références non attestées | 10 tests Debian PASS sur `5c408cf` ; validation Core à développer |
| Demo Studio V2 | `release/p0-demo-v2-ui-candidate-20261029-0004:app/portal/demo_v2.py` | Vue read-only de sources, états auth/unknown, timeline ; ancienne branche divergente (41 commits ahead, 24 behind lors de la comparaison) | Comparer avec `app/portal/demo_v2.py` non suivi du worktree historique avant toute importation |
| Contrat ACME Explore/Story | `feat/p0-acme-scenario-contract-20261028-1153:app/portal/acme_scenario_contract.py` | 9 checkpoints attendus (Grafana, n8n, GLPI), explicitement MISSING et non observés ; IDs simulés issus de fixture SHA | Réutiliser pour **objectifs de démonstration**, ne pas annoncer que les 9 étapes se sont réellement produites |
| Corrélation NOC/ITSM | `feat/acme-core-noc-itsm-correlation-20261027:app/portal/acme_itsm_correlation.py` | HMAC NOC + lecture Core, GLPI non attesté, état UNKNOWN par défaut | Étudier les contrats signés/tenant, éviter de promouvoir un ticket simulé en ticket réel |
| GLPI read-only | `feat/p1-glpi-real-http-ci-20261028-1035:app/shared/glpi_ticket_read.py` | Client HTTP lecture seule, HTTPS hors CI, taille réponse limitée, anti-redirection, contrôle entity, refus de source non vérifiée | Évaluer et porter dans un adapter privé, **jamais** exposer les tokens dans le portail |
| Golden Demo | `feat/golden-demo-journey-20261027:app/portal/golden_demo.py` | Contract read-only ; exécution `RUN_RECORDED` ne signifie pas evidence/approval/remediation | Utiliser comme parcours cible, non comme preuve |
| Topologie | `feat/p0-acme-enterprise-60ci-20261028-1115:db/migrations/005_seed_acme.sql` | Nœuds SAN, Payments, ERP, réseau, stockage identifiés | Vérifier les CI/edges et la migration avant intégration DB |
| Core actuel | `prep:app/core/main.py` | Run, événements, gates, proposals, demo-artifacts, receipts d'exécution déjà présents | Privilégier les contrats Core existants, pas de nouvelle DB sans besoin prouvé |
| Evidence actuel | `prep:app/core/demo_evidence_read.py` | Endpoint interne read-only de références synthétiques, qualifie la provenance sans retourner le payload brut | Réutiliser pour qualifier les evidence_ids avant de présenter une simulation comme liée à un run |

## Architecture cible — séparations de confiance

```text
ACME synthetic scenario (fixture) -> Core Run/Incident (DB)
     -> Evidence (refs, provenance, freshness) -> Analyst -> Critic
     -> Policy (synthetic SIMULATE; LIVE effects denied)
     -> remediation proposal (advisory, digest)
     -> HITL decision (fixture ONLY until authenticated workflow exists)
     -> what-if projection (pure Python, no side effects)
     -> run-bound receipt (SYNTHETIC_UNVERIFIED until Core/Evidence read checks)
     -> persisted read-model (future) -> Portal timeline (read-only)
     -> GLPI/n8n (future separate integration proof)
```

**Ne pas confondre** `RUN-ACME-OFFLINE-001` avec un Core Run persistant, `EVD-ACME-OFFLINE-001` avec une preuve observée, un `SIM-GLPI` avec un ticket GLPI, `authenticated=True` avec une vraie approbation ou `SIMULATED_SUCCESS` avec un service guéri.

## Incrément développé dans cette passe

- `app/shared/acme_remediation_projection.py` refuse désormais de projeter `HEALTHY` pour une recette d'inspection ou de ticket (statut `SIMULATED_NO_RECOVERY`).
- `tests/test_acme_remediation_projection.py` ajoute le cas de non-récupération par recette read-only.
- `app/shared/acme_demo_offline.py` offre une démo JSON **sans Docker** et reproductible pour SUCCESS/FAILURE, avec fixture datée, références explicitement non vérifiées, secrets masqués et `effect_applied=False`.
- `tests/test_acme_demo_offline.py` ajoute 4 tests de contrat (succès, échec, déterminisme, outcome interdit).
- Aucun appel réseau, SQL, shell, adaptateur ou effet d'infrastructure dans ce parcours.

## Gates / ordre de réalisation

**P0 — déjà acquis (preuves Debian)** : 28/28 tests du laboratoire/projection/receipt au SHA `5c408cf`, 26/26 préflight statique, sans Docker.

**P0 — qualification à refaire** : 1 test de projection supplémentaire, 4 tests CLI nouveaux, régression des 28 tests précédents ; au total **33 tests attendus** (10 labo + 9 projection + 10 receipt + 4 CLI), mais **non exécutés à ce stade**.

**P1 — prochaine implémentation** : validation read-only Core de l'identité du run, du mode et des evidence IDs, avec scope tenant et état UNKNOWN fail-closed ; corrélation du receipt au même run ; persist/read-model autorisés sans effet ; tests isolés.

**P1 — ensuite** : scénario SAN/Payments (la recette Linux ERP ne démontre pas une réparation SAN), UI Demo Studio V2 fusionnée après comparaison, intégration GLPI/n8n et Critic/Evidence, E2E staging.

**GO déploiement** uniquement après build, migrations et rollback testés sur projet/ports/volumes dédiés, secrets isolés, tests de non-régression, E2E et approbation explicite. Ne jamais installer dans `aiops2-rebuild` par défaut.

## Commandes offline de qualification proposées

```bash
python3 -m unittest discover -s tests -p 'test_remediation_lab.py' -v
python3 -m unittest discover -s tests -p 'test_acme_remediation_projection.py' -v
python3 -m unittest discover -s tests -p 'test_acme_remediation_receipt.py' -v
python3 -m unittest discover -s tests -p 'test_acme_demo_offline.py' -v
python3 -m app.shared.acme_demo_offline --outcome SUCCESS
python3 -m app.shared.acme_demo_offline --outcome FAILURE
python3 tools/acme_offline_source_preflight.py
```

La sortie CLI contient une hypothèse et non une preuve. Elle ne doit pas être interprétée comme un E2E de services.
