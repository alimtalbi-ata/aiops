# 2026-10-28 02:56 Europe/Paris — P0 portail, fail-closed navigateur

## Baseline et sources consultées
- Main initial : `0603e86a26978873c3b6196098674932d3378499`; PR #74 initiale : `91dc54b856746f83156e0d472d7b7798e4950e92`.
- PR #36, #37, #39, #41, #43 consultées (métadonnées et fichiers ciblés); PR #51, #57, #70 et #74 consultées pour éviter les conflits de portée. Continuité main `docs/PROJECT-CONTINUITY.md`, roadmap PR #39 et registre PR #36 lus. Réutilisation de la logique fail-closed de la PR #36 déjà portée dans #74, sans merge massif.
- `quality.yml` existant conservé, sans nouveau workflow ni accès à NVIDIA NGX.

## Incrément source
- PR existante : [#74](https://github.com/alimtalbi-ata/aiops/pull/74), branche `feat/p0-portal-bootstrap-read-auth-20261028-0204`.
- `app/portal/portal_bootstrap_client.js` : valide le schéma/provenance, les deux drapeaux d'attestation à `false`, les états UNKNOWN/READABLE_UNVERIFIED et les formes du read model **avant** tout rendu. Une réponse HTTP 200 contradictoire reste UNKNOWN.
- `tests/test_portal_bootstrap_client.mjs` : neuf mutations négatives de contrat, plus cas trois sources UNKNOWN, et fixture positive avec provenance explicite.
- `docs/portal/BOOTSTRAP-READ-AUTH-P0.md` : contrat, limites et qualification.
- Commits PR : `ee84a53f78e1a07bbad2808b69c06f8d9b002b67`, `68ee8170b9015b07a72b9d706a50c588f91d17fb`, `b3b9ffc32c494fe3384482ff973a922194bd42e7`.

## Incident d'écriture et restauration de main
- **Écart détecté et corrigé dans cette exécution** : une première écriture avec branche omise a créé par erreur `app/portal/portal_bootstrap_client.js` sur `main` (commit `c21076557545f898442a268839e2da03a615e525`). La restauration a nécessité `9b9557b61c9994443a36e70e4d1f6efb1b23b83e` puis suppression du fichier par `1ed749129e32ea9a8854c437c7de9a6a8b43e35b`.
- **Vérification GitHub : arbre Git de main après restauration `75357e7c25e899997c6feb997917904956ca56a6`, identique à celui du HEAD initial `0603e86`.** Historique main contient cependant trois commits supplémentaires; aucune réécriture forcée n'a été tentée.
- Mesure de prévention : toujours utiliser la chaîne explicite `branch` issue de `head` normalisé, ne jamais passer `undefined` à une opération d'écriture GitHub.

## Tests, preuves et limites
- Test local Node : **NOT_TESTED** (pas de copie réseau GitHub dans le conteneur local; DNS github.com indisponible).
- CI non destructive : [run 40618130314](https://github.com/alimtalbi-ata/aiops/actions/runs/40618130314) sur `68ee817` : **IN_PROGRESS au moment de la première vérification**. Vérifier le run du dernier commit documentaire `b3b9ffc` avant toute déclaration PASS.
- Tests d'intégration conteneurs réels Core/Twin/n8n/Thruk/Grafana/GLPI : **NOT_TESTED**. NVIDIA NGX/Mistral 192B : **NOT_TESTED**. Debian/portail 17777, captures LIVE et vidéo : **NOT_TESTED**. Les tests JS utilisent un DOM synthétique pour tester le comportement UI, pas un service simulé revendiqué comme intégration.
- Risques : PR #74 reste draft; conflits futurs avec #51/#57/#70; aucune isolation tenant globale; pas d'attestation de source runtime. Aucune fusion, aucun déploiement, aucune commande LIVE.
- Prochain micro-lot : vérifier le résultat CI du dernier commit, corriger tout échec; ensuite convergence RBAC des routes anciennes et tests d'intégration éphémères réels, sans toucher à Debian.
