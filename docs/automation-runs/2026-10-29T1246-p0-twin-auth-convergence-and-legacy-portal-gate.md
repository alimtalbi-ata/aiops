# 2026-10-29 12:46 CET — Release P0 5/5, convergence sans nouvelle PR

**READY_FOR_STABLE=BLOCKED / NO-GO.** Aucune promotion stable, aucun SSH/Debian, aucun Docker, aucune mutation LIVE. Échéance indicative du lot initial T+6h ~17:11 CET ; heure de ce contrôle ~12:46 CET (environ 4h25 restantes).

## État GitHub vérifié et base de décision

- `main=27deb9b1a66faf27df8d69b137a63451f7649d80`; `deploy/aiops2-stable=e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`. `stable...main` divergé : 43 ahead / 633 behind. Ne jamais fusionner main dans stable par force.
- PR unique [#185](https://github.com/alimtalbi-ata/aiops/pull/185), draft, base [#153](https://github.com/alimtalbi-ata/aiops/pull/153) `e5c6b030c374e47f64678f425df78cd147335eec`; HEAD avant correctif `4322e0e6c54d099eb56b44971652b4d484564d6f` : [quality.yml #40861297214](https://github.com/alimtalbi-ata/aiops/actions/runs/40861297214) **6/6 SUCCESS**, trois workflows historiques SUCCESS, **CI synthétique, pas E2E Debian**.
- Comparaison stable → HEAD avant correctif : 55 commits ahead / 0 behind, mais `deploy/*`, `.github/*`, Core, Twin, Policy, Portal et `compose.yml` ne sont pas transportés par le poller installé portal-only. Ascendance Git ≠ autorisation de déployer.
- Sources figées et déjà intégrées : #170 Twin `bec96d26b288394a8c4d878417090e09c8c52a25`, #171 NOC `a46b5d0972a10b78ac1a490257bf543592ba3c2b`, #176 Policy `b56488d9ff80c8166c9dd9cf64f24d0b7e3d48c8`, #156 Evidence/Recette `395707e4f4dbc0e15ce6fe44d64776b6f4375aeb`. UI #177 `a539b293d5bc01d6cd71ff6dc5b53b382baa793c` exclue : CI rouge à la dernière qualification.
- Derniers audits de propriétaires : [Twin sur #185](https://github.com/alimtalbi-ata/aiops/pull/185#issuecomment-6494983840), [NOC sur #185](https://github.com/alimtalbi-ata/aiops/pull/185#issuecomment-6495391308), [Policy sur #185](https://github.com/alimtalbi-ata/aiops/pull/185#issuecomment-6495535367), [UI sur #156](https://github.com/alimtalbi-ata/aiops/pull/156#issuecomment-6495056145). Aucun doublon de service, moteur de graphe, ledger ou workflow CI.

## Une correction P0 sur la PR existante : Twin fail-closed

Le SHA `4322e0e6` portait la traversée inverse sourcée SAN→Payments mais réintroduisait des routes Twin publiques et un `PASS` sur action synthétique inconnue ou cible absente. Correction ciblée **dans #185** (pas de micro-PR) :
- `app/twin/main.py` commit `f41789f06e37a5bee28ae4396708da18a081cfe3` : réutilise `require_twin_read_auth` existant sur `/acme-quality`, `/summary`, `/nodes`, `/graph`, `/at` ; réutilise le contrat `synthetic_event` de #170 (Bearer strict, action SET_STATE/OBSERVE, cible existante, payload valide, refus 422/404 **avant écriture**). Conserve l'impact inverse et `acme-quality`.
- `tests/test_internal_auth.py` commit `68f09395fec9e662a861e12b2e8562dd88a1f836` : quatre nouveaux tests ciblés refus anonyme sans DB, Bearer explicite, no-op 422 sans DB, cible absente 404 sans mutation. Réutilise la suite `quality.yml` existante.
- **CI nouvelle PENDING au moment de rédaction** : [quality.yml #40867835688](https://github.com/alimtalbi-ata/aiops/actions/runs/40867835688), autres workflows en cours/verts ; aucun test Debian ou local déclaré. Vérifier le HEAD final et les checks après ce journal ; ne pas attribuer la CI de `4322e0e6` à la correction.
- Restent non portés : auth metrics dédiée + provisioning Prometheus de #170, suite Twin HTTP/PostgreSQL de #170 ; `/metrics` est encore anonyme. **Aucun GO sécurité** tant que ces écarts ne sont pas qualifiés. Le Worker peut synthétiser la redondance sans preuve indépendante (audit #176) ; ne jamais afficher PASS comme sûreté indépendante. UI #177 ne peut pas être importée en bloc (CI rouge) ; identités de run/detail/polling non attestées.

## Matrice REUSE-FIRST / transport exact

| Besoin / owner | Existant (candidate) | Lacune prouvée / tests | Transport / restart / rollback |
|---|---|---|---|
| Twin SAN→Payments 1/5 | `app/twin/main.py:impact,require_twin_read_auth,synthetic_event,acme_quality`, #170 | auth/read/no-op corrigés, métriques et HTTP PostgreSQL non requalifiés | image `aiops2-twin` ciblée ; rollback image prévu, **terrain NOT_TESTED** |
| Portal/UI 2/5 | `app/portal/main.py:demo_run_detail,demo_status`, `demo_v2.py:render_demo_v2` | run/tenant mismatch et rendu V2 non raccordé (audit #177) | image `aiops2-portal`, restart ciblé, rollback **NOT_TESTED** |
| Core/NOC/Evidence 3/5 | `app/core/main.py:get_ai_ledger`, `demo_evidence_read.py`, `app/portal/demo_ledger_read.py` | références synthétiques non attestées ; tests fixtures verts | image Core/Portal ; rollback **NOT_TESTED** |
| Policy/HITL 4/5 | `app/policy/main.py:check`, `app/worker/main.py` conservé | `redundancy_ok` synthétique non vérifié ; ne pas annoncer approval LIVE | image Policy, Worker inchangé ; rollback **NOT_TESTED** |
| Release/E2E 5/5 | `deploy/deploy-acme-p0.py:plan,preflight_host,apply`, scripts `check_demo_*` | poller installé `deploy/poll-approved-deploy.sh` ne sait que Portal ; ownership et E2E Debian non attestés | images Core/Twin/Policy/Portal ciblées prévues, **aucun appel poller**, rollback Docker réel **NOT_TESTED** |

**Point de compatibilité P0 vérifié dans le code** : `deploy/deploy-demo-studio-v2.sh` crée le portail avec `docker run` et `docker network connect` (pas Compose). `deploy/deploy-acme-p0.py:inspect_owned` exige les labels `com.docker.compose.*` et un projet `aiops2-rebuild` pour **les quatre** conteneurs. Si le portail Debian actuel provient encore de cet installateur, le nouveau `--inspect-host` **refusera correctement** ce conteneur non possédé ; il ne faut ni le supprimer ni le « récupérer » implicitement. Il faut d'abord une qualification opérateur de la propriété réelle et une procédure de migration réversible approuvée, sans toucher aux données locales ni aux conteneurs tiers. Aucun constat de labels Debian n'est disponible.

## Gate et recette read-only

Réutiliser, sans créer de second script, `deploy/deploy-acme-p0.py --inspect-host`, `scripts/check_demo_field_readonly.py`, `scripts/check_demo_evidence_receipts.py` et `scripts/check_demo_release_receipts.py`. Sur SRV-DEB-05, **uniquement par opérateur autorisé** depuis un checkout propre au SHA candidat, avec le vrai chemin Compose validé :
```bash
export DOCKER_HOST=unix:///run/user/1001/docker.sock XDG_RUNTIME_DIR=/run/user/1001
python3 deploy/deploy-acme-p0.py --stable-sha e54c4e9a9b37e6229559a1b587c9a06b4741a8b3 --candidate-sha "$(git rev-parse HEAD)" --source-dir /ABSOLUTE/PATH/TO/EXISTING/COMPOSE --state-dir /home/aiops/aiops2-auto-deploy --inspect-host
```
Remplacer uniquement le placeholder par le répertoire réel. **Ne pas exécuter `--apply`**. Demander le reçu JSON horodaté, `applied.sha` attesté indépendamment, état du poller, quatre smoke-tests HTTP read-only sous auth, même `run_id/incident_id/evidence_ids`, `SIMULATE`, provenance synthetic, RBAC tenant et rollback observé. Un reçu `HOST_PREFLIGHT_PASS_UNATTESTED` conserve `overall=NO_GO`.

**Blocage principal unique de promotion : compatibilité/ownership de la chaîne de déploiement réelle non démontrée** (poller portal-only et portail potentiellement `docker run` hors Compose). Les régressions Twin/UI/Policy identifiées restent des risques de qualification supplémentaires, pas une permission de contourner le blocage. **READY_FOR_STABLE=BLOCKED**, `applied.sha`, Debian smoke, impact Payments runtime, Temporal, authenticité Evidence et E2E ACME **NOT_TESTED**. Prochain acte : recevoir préflight opérateur read-only et décider d'une migration réversible sous revue ; sinon démo Portal existante uniquement, avec UNKNOWN explicite.

## Addendum CI observée après intégration (SHA du journal initial `b1453a122967116a504b01e0e5427e29cac050e3`)

- [quality.yml #40867949473](https://github.com/alimtalbi-ata/aiops/actions/runs/40867949473) **completed/success, 6/6 jobs** : `database-migrations`, `migration-runner-upgrade`, `mariadb-dr-rehearsal`, `quality-build-package`, `runtime-e2e`, `release-kit`. Les logs du job `quality-build-package` confirment **4/4 nouveaux tests Twin PASS** au sein de `tests/test_internal_auth.py` (**8/8** tests du fichier) ; les 16 tests déployeur offline et 17 Evidence/agrégateur restent PASS. Le job `runtime-e2e` est synthétique CI, pas une attestation de run ACME sur Debian.
- [V2.8 #40867949437](https://github.com/alimtalbi-ata/aiops/actions/runs/40867949437), [Offline Integrity #40867949411](https://github.com/alimtalbi-ata/aiops/actions/runs/40867949411), [Historical Trace #40867949453](https://github.com/alimtalbi-ata/aiops/actions/runs/40867949453) : **completed/success** sur ce même SHA.
- Cette mise à jour documentaire crée un nouveau HEAD : **CI à requalifier sur le SHA final après commit**. Le statut GO ne change pas : **NO-GO / READY_FOR_STABLE=BLOCKED**, aucun test Debian ni rollback réel.
