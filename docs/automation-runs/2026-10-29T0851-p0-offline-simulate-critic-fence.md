# 2026-10-29 08:51 CET — Recette 5/5 : Critique nécessaire au PASS synthétique

## Inventaire GitHub et contrats relus
- HEAD main `27deb9b1a66faf27df8d69b137a63451f7649d80` ; HEAD `deploy/aiops2-stable` `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`. Aucune promotion.
- #153 déployeur `e5c6b030c374e47f64678f425df78cd147335eec` : `quality.yml` SUCCESS sur SHA ; transport seulement portail ciblé, pas Core/Twin/Copilot/Policy/Evidence.
- #156 Recette base `c391029a1b4aa6a5166a6d835f9a9eb753af96e5` : `quality.yml` SUCCESS sur SHA avant ce correctif.
- #170 Twin `3f14fe28970de39c8f320d123e6121a2459fccd8` : quality.yml SUCCESS isolée.
- #171 NOC/Evidence `93953c73f96537bc97a24f681fab047edd6d26fe` : quality.yml SUCCESS isolée ; le Portal réel refuse déjà `SIMULATE/PASS` sans Critique validée.
- #176 Policy `1741a3bf4a3e27cfc7ff66eab2a40763a9b82e24` : quality.yml SUCCESS isolée.
- #177 UI `b5b098692fa84f6ed5c27ebfa068d193af5a2dd0` : quality.yml FAILURE. #169 également bloquée.
- Consulté : `docs/automation-runs/2026-10-29T0746-p0-offline-evidence-receipt-join.md`, #171 `docs/automation-runs/2026-10-29T0821-p0-noc-real-http-simulate-critic.md`, et contrats #153/#156. Anciennes PR #140–#146 non intégrées aveuglément.

## Une livraison verticale mesurable
- Code `b34540e34b82d0286f6e812ec099e4d62831d374`, tests `25fbf8233f68fb1e575094b4fa16c04fa34198f4`.
- `scripts/check_demo_evidence_receipts.py` : refuse un `SIMULATE/PASS` si aucune Critique de la projection n'a `validated=true`. Avant, un reçu entièrement non validé pouvait passer le contrôle de cohérence hors ligne, contrairement au Portal #171.
- `tests/test_demo_evidence_receipts.py` : test négatif de Critique non validée et test positif qui maintient `policy_critic_linkage_origin=NOT_TESTED` et `overall=NO_GO`.
- Contrat de sortie `aiops.demo-evidence-offline-receipt.v1` inchangé ; condition nécessaire mais non suffisante. Les décisions projetées ne contiennent pas leur `critique_id` : le lien exact Policy→Critique ne peut être attesté par ces deux exports. Preuves synthétiques = références, jamais validation indépendante.
- Réutilisation du step `quality.yml` existant, aucun workflow supplémentaire, aucun changement HTTP, secret, LIVE ou déploiement.
- Tests locaux : NOT_TESTED (pas de checkout local réseau). CI du nouveau SHA : PENDING à la création du journal ; mise à jour de la preuve à effectuer après observation.

## Matrice GO/NO-GO
| Dimension | Qualification |
| --- | --- |
| Critique nécessaire au PASS synthétique sur fixtures | CI PENDING |
| Policy→Critique exacte, `incident_id`, Temporal | NOT_TESTED |
| Tenant A/B, SAN→Payments runtime, E2E Core→Temporal→Analyst/Critic→Policy→Evidence→Portal | NOT_TESTED |
| Déployeur Core/Twin/Copilot/Policy/Evidence (copie/rebuild/restart/tests/rollback) | BLOCKED — #153 portail uniquement |
| Portail Demo Studio V2 (copie/rebuild/restart) | Script ciblé #153, terrain NOT_TESTED |
| Rollback Docker, `applied.sha`, smoke-tests sur SRV-DEB-05 | NOT_TESTED |
| Promotion stable | NO-GO |

**READY_FOR_STABLE=BLOCKED.** Blocage unique : aucun déployeur multi-services avec rollback qualifié. Prochain acte : SHA figés par domaine, candidate intégrée unique, CI rapide puis complète, recette read-only, preuves Debian authentifiées. Aucune fusion stable, aucun accès Debian, aucune remédiation LIVE.
