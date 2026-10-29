# 2026-10-29 06:10 Europe/Paris — P0 UI : liaison stricte de l'impact Twin à SAN-A

## Références GitHub et coordination
- HEAD `main` vérifié : `27deb9b1a66faf27df8d69b137a63451f7649d80`; `deploy/aiops2-stable` : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`, **non modifiée**.
- PR candidate UI existante [#177](https://github.com/alimtalbi-ata/aiops/pull/177), branche `ui/p0-demo-v2-core-detail-envelope-20261029-0307`, base #169, empilant #140 → #150 → #152 → #158 → #166 → #169. Pas de nouvelle PR parallèle ni fusion.
- PR consultées : #141 fusionnée, #144 fermée non fusionnée ; #142/#143/#145/#146 ouvertes ; #153 déployeur, #156 Recette 5/5, #170 Twin, #171 NOC, #176 Policy ouvertes en draft. Journaux lus : `2026-10-29T0507-P0-demo-v2-twin-root-only-preflight.md` (#177), `2026-10-29T0048-p0-stable-transport-matrix.md` (#156), `2026-10-29T0543-p0-poller-workflow-transport-fence.md` (#153). Les checks isolés verts de #156/#170/#171 ne constituent pas un assemblage E2E.
- Commits de ce micro-lot : `7bf57f0641e91e754867d5a934dbf84ebab0a3bc` (code), `49bc66839fecdddc9e5803f0bbece4a5fdb2802c` (tests), `3f0b7d9be6572a979a77b0ea8277c1f45d4c3e32` (correction d'assertion HTML). Le SHA final après ce journal est à relever sur GitHub.

## UNE livraison verticale mesurable
- `app/portal/main.py` : l'impact Twin reçu pour `/api/twin/impact/ACME-SAN-FABRIC-A` est désormais rejeté si son `root` diffère de `ACME-SAN-FABRIC-A`, même s'il contient SAN-A et Payments dans `affected`. La même constante fixe la racine demandée et la racine validée.
- En cas de désaccord : préflight `INCONNU`, `impact_known=false`, `impact_ids=[]`. Aucun marquage d'impact trompeur ni causalité Payments déduite. Le chemin racine SAN-A valide conserve ses labels `RACINE SEULE / NON PROUVÉE` ou `NŒUDS DÉCLARÉS / NON ATTESTÉE`.
- `tests/test_v28_portal_ui.py` : deux tests ajoutés, un sur le contrat de validation et un sur le HTML + graphe en lecture seule. Les tests simulent une réponse Twin plausible mais concernant SAN-B et interdisent tout `post_json`.
- Contrat API Core/Twin/Copilot/Policy/Evidence **inchangé** ; seul le contrat de présentation du préflight SAN-A est durci, sans RBAC relâché ni effet LIVE.

## Résultats vérifiés
- Exécution locale du checkout : **NOT_TESTED** (GitHub accessible via connecteur, mais pas de clone réseau dans le conteneur). Aucun test Debian.
- Première CI du SHA tests `49bc6683` : [quality.yml #40821949410](https://github.com/alimtalbi-ata/aiops/actions/runs/40821949410) : étape UI **FAILURE**, une assertion cherchait une apostrophe non échappée dans le HTML. Le correctif `3f0b7d9b` ne modifie que l'assertion, pas le code de production.
- CI sur SHA code/tests corrigé `3f0b7d9b` : [quality.yml #40821997145](https://github.com/alimtalbi-ata/aiops/actions/runs/40821997145), job `quality-build-package` : **5 + 16 + 39 = 60/60 tests UI ciblés PASS**, dont les deux nouveaux ; étape `Policy safety unit tests` **FAILURE : 11 échecs sur 15**. La CI globale n'est donc pas verte. `runtime-e2e` et les autres jobs : **non conclus au relevé**. Les tests ciblés ne qualifient pas la chaîne ACME.
- `.github/workflows/quality.yml` existant réutilisé ; aucun workflow ajouté ni contournement de la CI rouge.

## Transport, limites et décision
- Déployeur #153 : `app/portal/main.py` n'est pas copié intégralement (injection partielle), contrairement à `demo_v2.py` et `tests/test_demo_v2.py`. **Ce correctif ne sera pas livré fidèlement par le déployeur actuel.** #156 doit qualifier une couverture complète, un rollback sûr et la recette post-déploiement.
- **NOT_TESTED** : navigateur authentifié, tenant/RBAC en conditions réelles, impact SAN→Payments, Core→Temporal→Analyst/Critic→Policy SIMULATE→Evidence→Portal, corrélation run/evidence, `applied.sha` authentique, smoke-tests, logs horodatés et rollback SRV-DEB-05. Le poller stable ne prouve pas E2E.
- **BLOCKED / READY_FOR_STABLE=false / NO-GO** : échéance 05h dépassée ; Policy rouge, Temporal non qualifié, transport incomplet, recette terrain absente. Aucun push `deploy/aiops2-stable`, aucune fusion, aucun accès Debian, aucun secret ni mutation LIVE.
- Prochain lot (Recette 5/5 #156) : figer un SHA intégré, valider les modules réellement transportés/rebuild/restart, corriger Policy/Temporal sans affaiblir le fail-closed, exécuter `quality.yml` intégralement puis faire attester séparément la recette read-only et le rollback par l'opérateur Debian. Ne pas promouvoir sur la seule réussite des tests UI.
