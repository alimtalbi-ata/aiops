# V2.13.15 — Visualisation des chemins SAN redondants

## Expérience
Ajout d'un dessin de deux chemins Fabric A et Fabric B. La scène initiale montre deux chemins illustratifs disponibles, les scènes de dégradation montrent **Fabric A dégradé (simulé)** tandis que B reste disponible. Les scènes Critic/Policy conservent la visibilité de la dégradation, afin que STOP_AUTO n'apparaisse pas comme une remédiation automatique. La conclusion décrit un état **illustratif non mesuré** : elle n'atteste ni reprise réelle ni résolution d'incident.

L'objectif est de rendre le lien entre panne SAN, service métier et sécurité des décisions facile à expliquer devant un client, sans surcharge narrative. Les notes, preuves et limitations restent accessibles à la demande.

## Sécurité
Aucune API ajoutée, aucun accès historique et aucun appel DGX/Core. Aucun chiffre ni KPI inventé. `SIMULATED_TARGET` affiché en permanence. La présence d'un chemin de secours sur le dessin ne garantit ni la redondance réelle ni les performances opérationnelles.

## Qualification
`tests/browser/qualify_v21315_star.py` vérifie la représentation nominale, le chemin A dégradé, la persistance de B, la phase STOP_AUTO, l'absence de fausse revendication de réparation, provenance, mobile et erreurs JS. Rejouer aussi les régressions V2.13.14 (11), V2.13.13 (15) et V2.13.12 (13). Ces tests doivent être exécutés avant toute déclaration de PASS.

Pour Debian, extraire dans une copie V2.13.15 depuis la branche de la PR #36, tester sous `file://`, construire une image candidate, vérifier routes et asset sous Docker isolé, puis seulement effectuer une bascule du seul portail sur 17777 avec rollback et contrôles 200/403. Aucun second portail.

## État
Version de référence déployée connue : V2.13.14. Cette V2.13.15 est publiée sur GitHub et n'est pas encore qualifiée sur Chromium ni déployée.
