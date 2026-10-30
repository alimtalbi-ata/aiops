# 2026-10-29 11:52 CET — P0 release manager 5/5, qualification hôte sans mutation

**Verdict: READY_FOR_STABLE=BLOCKED / NO-GO.** Aucune promotion de `deploy/aiops2-stable`, aucune intervention sur SRV-DEB-05. Échéance T+6h approximative vers 17:11 CET (T0 du lot précédent); horloge de cette exécution 11:52 CET.

## Références vérifiées avant changement

- `main=27deb9b1a66faf27df8d69b137a63451f7649d80`; `deploy/aiops2-stable=e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`, branche protégée. Comparaison stable → candidate précédente `e94fe78430fe0e92e56aa99ac44fad72a117d204`: **52 ahead / 0 behind** ; ne signifie ni déployabilité ni recette.
- PR d'intégration unique [#185](https://github.com/alimtalbi-ata/aiops/pull/185) (draft), base #153, HEAD précédent `e94fe78430fe0e92e56aa99ac44fad72a117d204`, `quality.yml` [40856295169](https://github.com/alimtalbi-ata/aiops/actions/runs/40856295169) **SUCCESS** (6 jobs) + trois workflows hérités SUCCESS. Le nouveau code `--inspect-host` a été committé en `c2cfff23086cf5fe3a18262dab71f6859ea2c923` et ses tests en `cd9bdb2881eaf2a1a08d23a84daf24f10392ed60`; **CI nouvelle PENDING** au moment de ce journal. Ne pas attribuer le succès du HEAD précédent aux nouveaux commits.
- Sources intégrées et figées dans #185: #170 Twin `bec96d26b288394a8c4d878417090e09c8c52a25`, #171 NOC/Evidence `a46b5d0972a10b78ac1a490257bf543592ba3c2b`, #176 Policy `b56488d9ff80c8166c9dd9cf64f24d0b7e3d48c8` (adaptation), #156 Recette `395707e4f4dbc0e15ce6fe44d64776b6f4375aeb`, #153 poller `e5c6b030c374e47f64678f425df78cd147335eec`. UI #177 `a539b293d5bc01d6cd71ff6dc5b53b382baa793c` exclue (CI rouge à l'audit précédent). Ces checks isolés ne qualifient pas la release.

## Livraison verticale: préflight opérateur en lecture seule

Le **même** `deploy/deploy-acme-p0.py` de #185 accepte désormais `--inspect-host`, mutuellement exclusif de `--apply`. Le mode inspect vérifie (1) ascendance Git et checkout propre de la candidate, (2) `applied.sha` local strictement égal au stable attendu, absence de `DEPLOYMENT_BLOCKED`, (3) identité Docker rootless, Compose projet et conteneurs appartenant à `aiops2-rebuild`, sains et au bon répertoire/config, (4) jeton viewer distinct et présent sans l'afficher. Il n'exécute que `git`, `docker info`, `docker compose config` et `docker inspect` ; **aucun build, up, restart, SSH, POST, écriture applied.sha, modification de fichier local ou mutation LIVE**. Résultat `HOST_PREFLIGHT_PASS_UNATTESTED / overall=NO_GO` ou refus code 2, sans contenu sensible.

Les tests supplémentaires dans `tests/test_deploy_acme_p0.py` vérifient le mode read-only et le refus d'un `applied.sha` périmé **avant tout appel Docker**. Tests réellement exécutés: CI du SHA précédent verte; CI des deux nouveaux commits **PENDING**, tests Debian **NOT_TESTED**, tests Docker réel **NOT_TESTED**. Le code réutilise `preflight_host`, `inspect_owned`, `verify_release_state` et la suite `quality.yml` existante. Pas de nouveau script ni workflow.

Recette à exécuter **uniquement par un opérateur autorisé**, depuis un checkout approuvé, propre et isolé au SHA exact, sur SRV-DEB-05 (pas de lancement par cette automatisation) :

```bash
export DOCKER_HOST=unix:///run/user/1001/docker.sock XDG_RUNTIME_DIR=/run/user/1001
python3 deploy/deploy-acme-p0.py \
  --stable-sha e54c4e9a9b37e6229559a1b587c9a06b4741a8b3 \
  --candidate-sha "$(git rev-parse HEAD)" \
  --source-dir /ABSOLUTE/PATH/TO/EXISTING/COMPOSE \
  --state-dir /home/aiops/aiops2-auto-deploy \
  --inspect-host
```

Remplacer uniquement `--source-dir` par le **répertoire existant vérifié**, ne pas inventer ce chemin. Ne pas exécuter `--apply`. Fournir sortie JSON horodatée, SHA Git et, séparément, attestations non sensibles de l'agent poller et des smoke-tests. Un résultat `PASS_LOCAL_ONLY` n'atteste ni l'origine indépendante de `applied.sha` ni le déploiement.

## Matrice anti-duplication et contrat de transport

| Besoin / owner | Existant réutilisé (SHA de #185 précédent) | Lacune exacte / adaptation | Contrat CI | Transport / restart / rollback |
|---|---|---|---|---|
| Core Run/Incident/Evidence (3/5) | `app/core/main.py:create,get_run,get_ai_ledger`; `app/core/demo_evidence_read.py:evidence_refs` | Jointure inter-services réelle non attestée; aucune nouvelle route | Ledger/Evidence fixtures | image Core ciblée / restart ciblé / image antérieure taguée, rollback terrain NOT_TESTED |
| Twin SAN→Payments (1/5) | `app/twin/main.py:impact,require_twin_read_auth` (#170) | arêtes sourcées et impact runtime Debian UNKNOWN; ne pas fabriquer Payments | contrats Twin existants | image Twin / restart ciblé / rollback terrain NOT_TESTED |
| Policy SIMULATE/HITL (4/5) | `app/policy/main.py:evaluate,check` (#176 adapté) | critic/confidence validés en CI, pas de lien E2E terrain | tests Policy existants | image Policy / restart ciblé / rollback terrain NOT_TESTED |
| NOC/Portal (2/5 et 3/5) | `app/portal/main.py:demo_studio`, `app/portal/demo_ledger_read.py:read_demo_ledger`, `app/portal/demo_v2.py:render_demo_v2` | UI #177 CI rouge exclue; aucun second ledger | 16 tests Ledger + 17 Evidence sur SHA précédent | image Portal / restart ciblé / rollback terrain NOT_TESTED |
| Temporal/Worker/Copilot | `app/worker/workflow.py:IncidentWorkflow.run` et services existants | stages peuvent être synthétiques; exécution E2E UNKNOWN | runtime-e2e CI ≠ Debian | **non modifiés**, ne pas prétendre qualification |
| Release (5/5) | `deploy/poll-approved-deploy.sh`, `deploy/deploy-acme-p0.py:plan,preflight_host,apply` | **poller installé ne transporte que le portail** et ne déclenche pas transaction multi-services; nouvelle inspection ne le modifie pas | `test_deploy_acme_p0.py` | migration poller / rollback terrain **NOT_TESTED** |

Contrat d'intégration: `run_id`, `incident_id`, `evidence_ids`, provenance `synthetic`, critic validée, Policy `SIMULATE/PASS`, RBAC tenant A/B, et preuves horodatées doivent être cohérents sur **un même run réel** avant GO. Les références Evidence ne constituent pas une validation indépendante. Aucun LIVE. `scripts/check_demo_field_readonly.py`, `scripts/check_demo_evidence_receipts.py`, `scripts/check_demo_release_receipts.py` existent déjà et ne sont pas dupliqués.

## Coordination et blocage unique

Ordres aux 4 propriétaires maintenus dans les commentaires de #170/#177/#171/#176: **NO_CHANGE** sauf défaut P0 démontré sur #185 ; ne pas ouvrir de nouvelle pile de PR. 1/5: confirmer Twin sourcé sans nouveaux endpoints; 2/5: isoler CI UI rouge, ne pas intégrer #177; 3/5: préserver ledger/refs et provenance; 4/5: préserver SIMULATE fail-closed sans remplacer Worker. Le propriétaire 5/5 conserve seul la décision stable.

**Blocage P0 unique: le chemin de déploiement terrain n'est pas qualifié (poller installé portail-only, propriété Compose et rollback non attestés).** Prochain acte: exécuter le nouveau `--inspect-host` **en lecture seule par un opérateur**, obtenir le reçu, puis décider si une migration du poller peut être revue sans déploiement non autorisé. Si préflight refuse, ne rien déployer. Si succès, cela reste NO-GO jusqu'à CI intégrée, rollback et recette terrain indépendants.

`READY_FOR_STABLE=BLOCKED`. `applied.sha` Debian, smoke Core/Twin/Copilot/Portal, SAN→Payments, Temporal, tenant RBAC et E2E ACME: **NOT_TESTED**.
