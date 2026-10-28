# 2026-10-29 00:48 Europe/Paris — P0 matrice de transport du candidat stable

## SHAs et coordination
- HEAD main lu : `64b9f9aa7abae4b35bda2bf881defbe062268bce` ; PR #156 départ `5fb1a4f3a51fde8b175c9dabd3010f7e8fa89960`.
- Stable `deploy/aiops2-stable` : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`, non modifiée. GitHub compare : main ahead 42, behind 633 (divergence).
- Candidats lus : #153 déployeur `289d3fc09721ac349b6b0330adf6cbd9e9c33934` (quality success), #170 Twin `8f22570260ea70be1c3ffda52d00cbfe453ec2f7` (success), #171 NOC `c7b143c64eb5127d9ae690fbf35799ee1ffb0ef6` (success), #169 UI `72238006f0eedc69e20aa15f6ed0950497778d8c` (un run failure). #140/#141/#142/#143/#144/#145/#146 examinées ; #141 fusionnée, #144 fermée non fusionnée.
- Journal des autres créneaux : `2026-10-29T0033-p0-policy-real-http-ci.md` (Policy HTTP CI qualifiée, chaîne métier non qualifiée).

## Micro-lot et contrat
- `scripts/check_demo_stable_coverage.py` : refuse désormais les changements de scripts `deploy/*` et de workflows `.github/workflows/*` non qualifiés, en accord avec le poller #153. Exige la présence du test copié `tests/test_demo_v2.py`.
- Sortie additive `module_deployment_matrix` : pour chaque chemin modifié, statut Git, copie, rebuild, restart, tests, rollback et décision. Contrat `aiops.demo-stable-deployment-coverage.v1` conservé ; plan **statique et non attesté**. `overall=NO_GO` reste constant.
- `tests/test_demo_stable_coverage.py` : quatre nouveaux tests Git locaux, négatifs et de non-régression.
- Déployeur #153 : copie seulement `app/portal/demo_v2.py` et `tests/test_demo_v2.py`, injection partielle `portal/main.py`, rebuild/restart portail uniquement. Core/Twin/Copilot/Policy/Evidence non transportés.
- Contrat à transmettre à #153/#169/#170/#171 : aucune PR de domaine n'est READY_FOR_STABLE sans transport, rollback et recette inter-services.

## Tests, risques, décision
- Tests locaux : NOT_TESTED avant push. CI `quality.yml` existante sur PR #156 : PENDING au commit, résultat à documenter dans la PR après exécution. Aucun workflow parallèle créé.
- Tests Debian, rollback Docker, `applied.sha` authentifié, isolation tenant inter-services, chaîne Core→Temporal→Analyst/Critic→Policy→Evidence→Portal et impact Payments : NOT_TESTED.
- **READY_FOR_STABLE=BLOCKED ; overall=NO_GO**. Aucun accès Debian, aucune fusion stable, aucune commande LIVE.
- Prochain acte : figer un SHA par domaine, préparer une candidate intégrée unique avec transport effectif et rollback de chaque composant, puis CI et recette read-only attestable.
