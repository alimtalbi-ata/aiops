# 2026-10-29 13:5x CET — release 5/5, Core DEMO PASS/SIMULATE guard on #185

**READY_FOR_STABLE=BLOCKED / NO-GO.** Candidate commune [#185](https://github.com/alimtalbi-ata/aiops/pull/185) (base #153, **pas** stable). Ce passage ne crée ni PR, ni workflow, ni déploiement. Le correctif est un contrat Core P0 dans la candidate existante, pas une nouvelle fonctionnalité.

## État vérifié avant modification

- `main=27deb9b1a66faf27df8d69b137a63451f7649d80`; `deploy/aiops2-stable=e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`. Candidate précédente `1d0e600c09665863c7cf3112942673b706e8e49b`, 60 commits ahead / 0 behind stable, **pas** autorisation de promotion.
- [quality.yml #40873758737](https://github.com/alimtalbi-ata/aiops/actions/runs/40873758737) sur ce SHA précédent: **6/6 SUCCESS**; [V2.8 #40873758894](https://github.com/alimtalbi-ata/aiops/actions/runs/40873758894), [Offline #40873758710](https://github.com/alimtalbi-ata/aiops/actions/runs/40873758710), [Historical #40873758762](https://github.com/alimtalbi-ata/aiops/actions/runs/40873758762): **SUCCESS**. Ces checks **ne qualifient pas** le SHA final du présent correctif.
- La correction NOC du préflight est déjà intégrée dans ce SHA précédent : `GET /api/noc/runs/SMOKE-UNAUTH/evidence-refs` remplace la route inexistante; HTTP 404 reste refusé, HTTP 401 attendu. Aucun nouvel endpoint.
- [Reçu opérateur Debian](https://github.com/alimtalbi-ata/aiops/pull/185#issuecomment-6496493005) sur **l'image antérieure e94fe784**, non vérifié indépendamment : quatre images Core/Twin/Policy/Portal Compose-owned et healthy, rootless, quatre images de rollback présentes mais **rollback non exercé**, santé HTTP 4/4 et page Portal PASS. Cron `deploy/aiops2-stable` **portal-only**, `applied.sha=e54c4e9`; les 4 images e94fe784 ne signifient **pas** stable appliqué. Run `RUN-0C526578309EE09A`, incident `INC-DEMO-ENRICHED-e2fa126fb136` : Analyst PASS, Critic BLOCKED, Policy 0, provenance SYNTHETIC_ONLY. **Pas de preuve E2E Payments/Policy SIMULATE.** Le Worker et smoke opérateur contiennent des modifications locales non committées : ne pas écraser.
- [Reçu opérateur 401 sur route canonique](https://github.com/alimtalbi-ata/aiops/pull/185#issuecomment-6496619221) depuis image e94fe784 : valable uniquement pour ce SHA/image, **pas** pour le HEAD actuel.

## Défaut contractuel P0 et correction minimale REUSE-FIRST

Sur la candidate précédente, `app/worker/main.py:execute_stage` traite `pol['state']=='PASS'` comme progression même si `decision!='SIMULATE'`. `app/core/main.py:gate` et `persist_policy_decision` n'imposaient pas ce couple pour un run DEMO. Une réponse `PASS/ALLOW` d'un service Policy divergent pouvait être persistée comme gate PASS, sans garantie de simulation. **Inspection statique, pas exploitation observée.**

- Commit Core `54456e4edb757b69f9d1123e4649fe4c2e951561` : dans les handlers **existants** `gate` et `persist_policy_decision`, lire le mode canonique du run en DB ; pour `DEMO/REPLAY/STORY`, rejeter `PASS` sans `SIMULATE` avec HTTP 422 **avant toute insertion**. Préserver les réponses `BLOCKED/ENRICH` et `UNKNOWN/ENRICH` ainsi que `PASS/SIMULATE`. Worker et Policy inchangés ; aucun second moteur, endpoint, schéma, ledger.
- Commit tests `b19008c556dce6e302c5c1362905377f00a2118f` : trois tests ciblés ajoutés à `tests/test_internal_auth.py` dans la CI `quality.yml` existante (rejet gate, rejet policy-record, conservation SIMULATE).
- Contrat modifié : Core POST `/api/runs/{rid}/gates` (stage POLICY) et POST `/api/runs/{rid}/policy-record` refusent désormais un PASS non SIMULATE sur run synthétique. Aucun changement des schémas JSON de succès.
- Limite importante : le Worker `redundancy_ok=True` dès une source synthétique et les stages HITL/REMEDIATE simulés restent **non attestés indépendamment** ; ce patch ne transforme pas les références Evidence en preuve de sécurité.

## Matrice anti-duplication et transport

| Besoin / propriétaire | Code existant et source figée | Lacune / adaptation minimale | Tests et transport / rollback |
|---|---|---|---|
| 1/5 Twin SAN→Payments | `app/twin/main.py:impact` #170 `bec96d2` | chemin sourcé synthétique conservé ; `/metrics` encore non qualifié | tests auth candidate, HTTP/Postgres terrain NOT_TESTED ; image Twin ciblée, rollback réel NOT_TESTED |
| 2/5 UI identité run/tenant | `app/portal/main.py:demo_run_detail,demo_status,timeline_page`, #177 `a539b29` | refuser détail/événements étrangers avant rendu, ne pas importer UI rouge en bloc | tests tenant/run à qualifier ; image Portal ciblée, rollback NOT_TESTED |
| 3/5 NOC/Evidence | `app/core/demo_evidence_read.py`, `app/portal/demo_ledger_read.py` #171 `a46b5d0` | correction route préflight déjà intégrée, aucune duplication | 401 route canonique sur image e94fe784 observé ; E2E NOT_TESTED |
| 4/5 Policy/HITL | `app/policy/main.py:evaluate` #176 `b56488d`, Worker V2.2 conservé | pas de PASS sans Critic/sûreté ; nouvelle garde Core PASS/SIMULATE | 3 tests Core ajoutés ; Worker synthétique reste risque ; Core image ciblée |
| 5/5 Release | `deploy/deploy-acme-p0.py:plan,preflight_host,apply` et `scripts/check_demo_* ` | déployeur candidat 4 images, **poller installé portal-only**, pas d'appel automatique | ownership 4/4 rapporté pour e94fe784, rollback réel et recette HEAD NOT_TESTED |

**Blocage principal unique :** chaîne de promotion/rollback réellement installée non qualifiée : cron portal-only, candidate multi-images non câblée, rollback non exercé. La présence de quatre images saines sur Debian à e94fe784 ne qualifie ni le HEAD de #185 ni un SHA stable promu. **Aucun push stable.**

## Recette suivante en lecture seule et garde release

1. Vérifier `quality.yml` et les autres checks **sur le HEAD exact après ce journal** ; ne pas recycler les checks précédents.
2. Opérateur autorisé uniquement : checkout **propre et isolé** au SHA exact, `deploy/deploy-acme-p0.py --inspect-host` avec chemin Compose réel et `applied.sha` opérateur ; puis `scripts/check_demo_field_readonly.py` sur les quatre loopbacks, sans POST, en conservant `overall=NO_GO`. Ne pas modifier les checkouts locaux sales, ni les stacks tierces, ni cron, ni `applied.sha`.
3. Recueillir reçus horodatés, image SHA, refus anonyme 401, run/incident/evidence identiques, Critic et Policy SIMULATE ou BLOCKED explicites, provenance SYNTHETIC_ONLY, RBAC tenant, rollback observé. **Sans attestation complète : NO-GO.**

**Tests locaux : NOT_TESTED. Tests Docker/Temporal/E2E sur SHA final : NOT_TESTED. applied.sha du SHA final : NOT_ATTESTED. Aucune mutation LIVE.**
